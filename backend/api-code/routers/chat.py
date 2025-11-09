from __future__ import annotations

from fastapi import APIRouter, HTTPException

from schemas import ChatRequest, ChatResponse
from services import GeminiChatService


def build_chat_router(chat_service: GeminiChatService) -> APIRouter:
    """Create the chat router wired to the provided chat service."""
    router = APIRouter(prefix="/api/v1", tags=["chat"])

    @router.post("/chat", response_model=ChatResponse)
    async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
        try:
            reply = await chat_service.generate_reply(payload.message)
        except ValueError as exc:  # Defensive guard; should be caught upstream.
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        return ChatResponse(reply=reply, model=chat_service.model_name)

    return router
