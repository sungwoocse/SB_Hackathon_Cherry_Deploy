from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

try:
    import google.generativeai as genai
except ImportError as exc:  # pragma: no cover - dependency managed via requirements.txt
    raise RuntimeError(
        "google-generativeai 패키지가 설치되어야 합니다. requirements.txt를 확인하세요."
    ) from exc


logger = logging.getLogger("cherry-deploy.chat")

GEMINI_MODEL_NAME = "gemini-2.5-flash"


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
