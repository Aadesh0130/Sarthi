"""
AI Travel Assistant service (spec sections 4E/17).

If neither provider is configured, `run_chat` returns configured=False and a
clear message -- the frontend must show this honestly rather than
pretending the assistant is working. When a key IS configured, the
assistant can only act through the tool functions in app/ai/tools.py -- it
cannot query the database or the internet directly.

AI_PROVIDER selects which backend answers ("openai" or "gemini"); both
implement the same app.integrations.base.AIProvider interface, so this file
never has provider-specific logic.
"""
import json

from sqlalchemy.orm import Session

from app.ai.tools import TOOL_SPECS, dispatch_tool
from app.core.config import get_settings
from app.integrations.base import AIProvider, ProviderError
from app.integrations.gemini import GeminiProvider
from app.integrations.openai_provider import OpenAIProvider
from app.schemas.ai import ChatMessage, ChatResponse

SYSTEM_PROMPT = (
    "You are Sarthi, an AI travel assistant for Indian tourism. Use the provided tools to look up real "
    "places, weather, events, hotels, cultural information and recommendations before answering -- never "
    "invent place names, ratings, opening hours, prices, event dates or weather. If a tool has no results "
    "or reports itself unconfigured, say so plainly rather than filling the gap yourself. Keep answers "
    "concise and actionable, and mention when something (like a route, price or event) came from a "
    "specific tool/provider. If the traveller mentions a destination feeling crowded/busy, or asks for a "
    "quieter/less crowded alternative, use rebalance_destination -- it is the only source of truth for "
    "tourism pressure, alternatives, distances and scores; never invent or estimate any of those yourself."
)

MAX_TOOL_ROUNDS = 4


def _get_provider() -> AIProvider | None:
    settings = get_settings()
    if not settings.ai_configured:
        return None
    if settings.ai_provider.lower() == "gemini":
        return GeminiProvider()
    return OpenAIProvider()


async def run_chat(db: Session, messages: list[ChatMessage]) -> ChatResponse:
    settings = get_settings()
    provider = _get_provider()
    if provider is None:
        env_var = "GEMINI_API_KEY" if settings.ai_provider.lower() == "gemini" else "OPENAI_API_KEY"
        return ChatResponse(
            configured=False,
            message=(
                f"The AI Travel Assistant isn't configured yet. Set {env_var} in backend/.env to enable it "
                f"(current AI_PROVIDER={settings.ai_provider}). Until then, Explore and the Trip Planner "
                "still work fully on real map/weather/places data -- just without natural-language chat."
            ),
        )

    history: list[dict] = [{"role": m.role, "content": m.content} for m in messages]
    tool_call_log: list[dict] = []

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            result = await provider.chat(SYSTEM_PROMPT, history, TOOL_SPECS)
        except ProviderError as exc:
            return ChatResponse(
                configured=True, provider=provider.name,
                message=f"The AI assistant is temporarily unavailable ({exc.detail}). Real place/weather/route data is unaffected.",
            )

        if not result.tool_calls:
            return ChatResponse(configured=True, provider=provider.name, reply=result.text or "", tool_calls=tool_call_log)

        history.append(result.assistant_message)
        for tc in result.tool_calls:
            tool_result = await dispatch_tool(db, tc["name"], tc["arguments"])
            tool_call_log.append({"name": tc["name"], "arguments": tc["arguments"]})
            history.append({
                "role": "tool", "tool_call_id": tc["id"], "name": tc["name"],
                "content": json.dumps(tool_result)[:6000],
            })

    return ChatResponse(
        configured=True, provider=provider.name,
        reply="I gathered some data but need another step to finish -- please ask me to continue.",
        tool_calls=tool_call_log,
    )
