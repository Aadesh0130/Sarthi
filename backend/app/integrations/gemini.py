"""
Google Gemini implementation of AIProvider (spec section 4E).

Uses a plain httpx POST to the generateContent REST endpoint rather than the
google-genai SDK, matching the lightweight, dependency-free style already
used for Nominatim/Overpass/OSRM/Open-Meteo (and avoiding another compiled
dependency on top of the pydantic-core build issue already hit on Windows).

Auth: `x-goog-api-key` header (current recommended pattern; the legacy
`?key=` query param still works but is being phased out).
Docs: https://ai.google.dev/api/generate-content
"""
import asyncio
import base64
import json

import httpx

from app.core.config import get_settings
from app.integrations.base import AIChatResult, AIProvider, ProviderError

settings = get_settings()


def _to_gemini_tools(tools: list[dict]) -> list[dict]:
    return [{"functionDeclarations": tools}] if tools else []


def _to_gemini_contents(messages: list[dict]) -> list[dict]:
    contents: list[dict] = []
    pending_function_responses: list[dict] = []

    def flush_pending():
        if pending_function_responses:
            contents.append({"role": "user", "parts": list(pending_function_responses)})
            pending_function_responses.clear()

    for m in messages:
        if m["role"] == "tool":
            try:
                response_obj = json.loads(m["content"])
            except (json.JSONDecodeError, TypeError):
                response_obj = {"result": m.get("content", "")}
            if not isinstance(response_obj, dict):
                response_obj = {"result": response_obj}
            pending_function_responses.append({"functionResponse": {"name": m.get("name", ""), "response": response_obj}})
            continue

        flush_pending()
        if m["role"] == "assistant":
            parts = []
            if m.get("content"):
                parts.append({"text": m["content"]})
            for tc in m.get("tool_calls", []) or []:
                parts.append({"functionCall": {"name": tc["name"], "args": tc["arguments"]}})
            if not parts:
                parts = [{"text": ""}]
            contents.append({"role": "model", "parts": parts})
        else:  # "user"
            contents.append({"role": "user", "parts": [{"text": m.get("content", "")}]})

    flush_pending()
    return contents


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.base_url = settings.gemini_base_url

    async def _post_with_retry(self, url: str, body: dict, timeout: float = 30.0, max_attempts: int = 3) -> dict:
        """Real-world fix (2026-09-16): Gemini (like any hosted LLM API) returns an
        occasional transient 503 "Service Unavailable"/502/504 under its own load --
        this is genuinely common for gemini-2.5-flash at peak times and, per Google's
        own docs, is usually resolved by a short retry, not evidence of anything wrong
        on our side. The old code surfaced this to the traveller as an immediate hard
        failure on the very first 503. This never fabricates a response on failure --
        it only gives the SAME real request a couple of short, honest extra attempts
        before reporting unavailable, exactly as a browser reloading a flaky page
        would. Auth failures (401/403) and rate limits (429) are NOT retried here --
        retrying those immediately would just fail the same way again."""
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.post(url, json=body, headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"})
                    if resp.status_code in (401, 403):
                        raise ProviderError("gemini", f"Authentication failed ({resp.status_code}) -- check GEMINI_API_KEY")
                    if resp.status_code == 429:
                        raise ProviderError("gemini", "Gemini rate limit exceeded")
                    if resp.status_code >= 500:
                        raise httpx.HTTPStatusError(
                            f"Server error '{resp.status_code}' for url '{url}'", request=resp.request, response=resp
                        )
                    resp.raise_for_status()
                    return resp.json()
            except ProviderError:
                raise  # auth/rate-limit: not retryable, surface immediately
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    await asyncio.sleep(0.6 * (attempt + 1))  # 0.6s, then 1.2s
                    continue
        raise ProviderError("gemini", str(last_exc)) from last_exc

    async def chat(self, system_prompt: str, messages: list[dict], tools: list[dict]) -> AIChatResult:
        body = {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": _to_gemini_contents(messages),
        }
        gemini_tools = _to_gemini_tools(tools)
        if gemini_tools:
            body["tools"] = gemini_tools

        url = f"{self.base_url}/models/{self.model}:generateContent"
        data = await self._post_with_retry(url, body)

        candidates = data.get("candidates", []) or []
        if not candidates:
            block_reason = (data.get("promptFeedback", {}) or {}).get("blockReason")
            if block_reason:
                raise ProviderError("gemini", f"Response blocked: {block_reason}")
            return AIChatResult(text="")

        parts = (candidates[0].get("content", {}) or {}).get("parts", []) or []
        text_parts = [p["text"] for p in parts if "text" in p]
        function_calls = [p["functionCall"] for p in parts if "functionCall" in p]

        text = "\n".join(text_parts) if text_parts else None

        if not function_calls:
            return AIChatResult(text=text or "")

        tool_calls = [
            {"id": f"call_{i}", "name": fc["name"], "arguments": fc.get("args", {})}
            for i, fc in enumerate(function_calls)
        ]
        assistant_message = {"role": "assistant", "content": text or "", "tool_calls": tool_calls}
        return AIChatResult(text=text, tool_calls=tool_calls, assistant_message=assistant_message)

    async def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> AIChatResult:
        """Gemini vision: inlineData image part alongside the text prompt, no
        tools -- used for photo-based place identification (spec section 15)."""
        body = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}},
                    ],
                }
            ]
        }
        url = f"{self.base_url}/models/{self.model}:generateContent"
        data = await self._post_with_retry(url, body, timeout=45.0)

        candidates = data.get("candidates", []) or []
        if not candidates:
            block_reason = (data.get("promptFeedback", {}) or {}).get("blockReason")
            raise ProviderError("gemini", f"Response blocked: {block_reason}" if block_reason else "No response from Gemini vision.")

        parts = (candidates[0].get("content", {}) or {}).get("parts", []) or []
        text = "\n".join(p["text"] for p in parts if "text" in p)
        return AIChatResult(text=text)
