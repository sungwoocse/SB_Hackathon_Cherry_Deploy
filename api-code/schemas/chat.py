from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message for the chatbot.")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Chatbot-generated response.")
    model: str = Field(..., description="Backend model identifier.")
