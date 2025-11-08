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
from repositories import DeployTaskRepository, InMemoryDeployTaskRepository  # noqa: E402
from routers import (  # noqa: E402
    build_auth_router,
    build_chat_router,
    build_deploy_router,
    build_health_router,
)
from services import AuthService, DeployService, GeminiChatService  # noqa: E402
from settings import get_settings  # noqa: E402


load_local_env()
settings = get_settings()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cherry-deploy")

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
deploy_repository: DeployTaskRepository | InMemoryDeployTaskRepository = DeployTaskRepository()
deploy_service = DeployService(deploy_repository, settings)
auth_service = AuthService(settings)
auth_dependency = auth_service.build_auth_dependency()

app.include_router(build_chat_router(chat_service))
app.include_router(build_auth_router(auth_service))
app.include_router(build_deploy_router(deploy_service, auth_dependency))
app.include_router(build_health_router(deploy_service))


@app.on_event("startup")
async def on_startup() -> None:
    global deploy_repository, deploy_service  # pylint: disable=global-statement
    try:
        await deploy_repository.ensure_indexes()
        logger.info("MongoDB repository initialized successfully.")
    except Exception as exc:  # pylint: disable=broad-except
        logger.warning(
            "MongoDB unavailable (%s); falling back to in-memory repository.", exc
        )
        deploy_repository = InMemoryDeployTaskRepository()
        deploy_service.repository = deploy_repository  # type: ignore[assignment]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app_main:app", host="0.0.0.0", port=9001, reload=True)
