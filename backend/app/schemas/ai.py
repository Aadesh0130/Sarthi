from typing import Optional

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    destination_query: Optional[str] = None


class ChatResponse(BaseModel):
    configured: bool
    provider: Optional[str] = None  # "openai" | "gemini" -- which AI provider actually answered
    reply: Optional[str] = None
    tool_calls: list[dict] = []
    message: Optional[str] = None  # set when not configured
