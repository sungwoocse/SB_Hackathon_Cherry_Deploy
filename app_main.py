from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parent
API_CODE_PATH = PROJECT_ROOT / "api-code"
if str(API_CODE_PATH) not in sys.path:
    sys.path.insert(0, str(API_CODE_PATH))

from env_loader import load_local_env  # noqa: E402
from routers import build_chat_router, health_router  # noqa: E402
from services import GeminiChatService  # noqa: E402
from settings import get_settings  # noqa: E402


load_local_env()
settings = get_settings()

logging.basicConfig(level=logging.INFO)

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

chat_service = GeminiChatService(api_key=settings.gemini_api_key)

app.include_router(build_chat_router(chat_service))
app.include_router(health_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_main:app", host="0.0.0.0", port=9001, reload=True)
