from __future__ import annotations

from typing import Optional

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
except ImportError as exc:  # pragma: no cover - allow tests without motor
    AsyncIOMotorClient = None  # type: ignore
    AsyncIOMotorDatabase = None  # type: ignore
    _motor_import_error = exc
else:
    _motor_import_error = None

from settings import get_settings


_client: Optional[AsyncIOMotorClient] = None


def get_mongo_client() -> AsyncIOMotorClient:
    if AsyncIOMotorClient is None:
        raise RuntimeError(
            "motor is not installed; install the dependency or set DEPLOY_DRY_RUN to use a stub repository."
        ) from _motor_import_error
    global _client
    if _client is None:
        settings = get_settings()
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_database() -> AsyncIOMotorDatabase:
    if AsyncIOMotorDatabase is None:
        raise RuntimeError(
            "motor is not installed; MongoDB access is unavailable in this environment."
        ) from _motor_import_error
    settings = get_settings()
    client = get_mongo_client()
    return client[settings.mongodb_db_name]
