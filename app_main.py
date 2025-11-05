from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Optional

import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

try:
    import google.generativeai as genai
except ImportError as exc:  # pragma: no cover - dependency managed via requirements.txt
    raise RuntimeError(
        "google-generativeai 패키지가 설치되어야 합니다. requirements.txt를 확인하세요."
    ) from exc


def _load_local_env(env_path: Path = Path(".env")) -> None:
    """Minimal .env loader so local runs pick up secrets without extra deps."""
    if not env_path.exists():
        return

    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            logging.warning("Skipping malformed .env line: %s", raw_line)
            continue
        key, value = line.split("=", 1)
        clean_key = key.strip()
        clean_value = value.strip().strip('"').strip("'")
        os.environ[clean_key] = clean_value


_load_local_env()


class Settings(BaseModel):
    """Runtime configuration resolved from environment variables."""

    gemini_api_key: Optional[str] = Field(
        default=None, alias="GEMINI_API_KEY", description="Google Gemini API key"
    )

    @classmethod
    def from_env(cls) -> "Settings":
        return cls.model_validate(os.environ)


settings = Settings.from_env()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cherry-deploy")

GEMINI_MODEL_NAME = "gemini-2.5-flash"

app = FastAPI(
    title="Delightful Deploy API",
    version="0.1.0",
    description="Unified DevOps + chatbot backend for Team Cherry.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message for the chatbot.")


class ChatResponse(BaseModel):
    reply: str = Field(..., description="Chatbot-generated response.")
    model: str = Field(..., description="Backend model identifier.")


class GeminiChatService:
    """Simple facade for Gemini integration (placeholder until API key provided)."""

    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key
        self.model_name = GEMINI_MODEL_NAME

    async def generate_reply(self, prompt: str) -> str:
        if not prompt:
            raise ValueError("Prompt must be a non-empty string.")

        if not self.api_key:
            logger.warning("GEMINI_API_KEY missing; falling back to static response.")
            return self._fallback_response(prompt)

        try:
            response_text = await asyncio.to_thread(self._call_gemini, prompt)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Gemini 호출 실패, fallback 사용: %s", exc)
            return self._fallback_response(prompt)

        if not response_text:
            logger.warning("Gemini 응답이 비어있습니다. fallback 사용.")
            return self._fallback_response(prompt)

        return response_text

    def _call_gemini(self, prompt: str) -> str:
        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model_name)
        response: Any = model.generate_content(prompt)
        if hasattr(response, "text") and response.text:
            return response.text.strip()

        # candidates/parts 구조를 직접 탐색
        candidates = getattr(response, "candidates", None) or []
        for candidate in candidates:
            parts = getattr(candidate, "content", None)
            if not parts:
                continue
            for part in getattr(parts, "parts", []):
                text = getattr(part, "text", None)
                if text:
                    return text.strip()

        return ""

    @staticmethod
    def _fallback_response(prompt: str) -> str:
        return (
            "안녕하세요! Gemini 연동 준비 중이라 간단한 에코 답변을 드릴게요. "
            f"(message='{prompt[:150]}')"
        )


chat_service = GeminiChatService(
    api_key=settings.gemini_api_key,
)


@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest) -> ChatResponse:
    """
    Lightweight chatbot endpoint used by the frontend during the hackathon MVP.
    """
    try:
        reply = await chat_service.generate_reply(payload.message)
    except ValueError as exc:  # Defensive guard; should be caught upstream.
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ChatResponse(reply=reply, model=chat_service.model_name)


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    """Basic liveness probe for PM2 / monitoring tooling."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_main:app", host="0.0.0.0", port=9001, reload=True)
