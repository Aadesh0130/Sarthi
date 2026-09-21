"""
OpenAI implementation of AIProvider (spec section 4E).

Reconstructs the full generic conversation history into OpenAI's native
chat.completions format on every call -- this keeps app/services/ai_service.py
and app/ai/tools.py completely provider-agnostic.
"""
import base64
import json

from app.core.config import get_settings
from app.integrations.base import AIChatResult, AIProvider, ProviderError

settings = get_settings()


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    return [{"type": "function", "function": t} for t in tools]


def _to_openai_messages(system_prompt: str, messages: list[dict]) -> list[dict]:
    out = [{"role": "system", "content": system_prompt}]
    for m in messages:
        if m["role"] == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"])},
                    }
                    for tc in m["tool_calls"]
                ],
            })
        elif m["role"] == "tool":
            out.append({"role": "tool", "tool_call_id": m["tool_call_id"], "content": m["content"]})
        else:
            out.append({"role": m["role"], "content": m.get("content", "")})
    return out


class OpenAIProvider(AIProvider):
    name = "openai"

    def __init__(self):
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    async def chat(self, system_prompt: str, messages: list[dict], tools: list[dict]) -> AIChatResult:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderError("openai", "The 'openai' package is not installed on the server.") from exc

        client = AsyncOpenAI(api_key=self.api_key)
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=_to_openai_messages(system_prompt, messages),
                tools=_to_openai_tools(tools),
                tool_choice="auto",
            )
        except Exception as exc:  # openai raises its own APIError subclasses
            raise ProviderError("openai", str(exc)) from exc

        msg = resp.choices[0].message
        if not msg.tool_calls:
            return AIChatResult(text=msg.content or "")

        tool_calls = [
            {"id": tc.id, "name": tc.function.name, "arguments": json.loads(tc.function.arguments or "{}")}
            for tc in msg.tool_calls
        ]
        assistant_message = {"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls}
        return AIChatResult(text=msg.content, tool_calls=tool_calls, assistant_message=assistant_message)

    async def analyze_image(self, image_bytes: bytes, mime_type: str, prompt: str) -> AIChatResult:
        """OpenAI vision: image passed as a data: URI content part -- used for
        photo-based place identification (spec section 15). Requires a
        vision-capable OPENAI_MODEL (e.g. gpt-4o-mini or later)."""
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:
            raise ProviderError("openai", "The 'openai' package is not installed on the server.") from exc

        data_uri = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        client = AsyncOpenAI(api_key=self.api_key)
        try:
            resp = await client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }],
            )
        except Exception as exc:
            raise ProviderError("openai", str(exc)) from exc

        msg = resp.choices[0].message
        return AIChatResult(text=msg.content or "")
