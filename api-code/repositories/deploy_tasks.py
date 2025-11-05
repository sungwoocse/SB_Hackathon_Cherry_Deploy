from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

try:
    from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase
except ImportError:  # pragma: no cover - fallback for test environments
    AsyncIOMotorCollection = Any  # type: ignore
    AsyncIOMotorDatabase = Any  # type: ignore
try:
    from pymongo import ReturnDocument
except ImportError:  # pragma: no cover - fallback for test environments
    class _ReturnDocument:
        AFTER = True

    ReturnDocument = _ReturnDocument()  # type: ignore

from db.mongo import get_database
from domain.deploy_states import DeployStatus
from models.deploy import DeployReport, DeployTask, DeployTaskCreate, DeployTaskUpdate


class DeployTaskRepository:
    """MongoDB repository handling deploy_tasks and deploy_reports collections."""

    def __init__(self, database: Optional[AsyncIOMotorDatabase] = None):
        self._db = database or get_database()
        self._tasks: AsyncIOMotorCollection = self._db["deploy_tasks"]
        self._reports: AsyncIOMotorCollection = self._db["deploy_reports"]

    async def ensure_indexes(self) -> None:
        await self._tasks.create_index("status")
        await self._tasks.create_index("started_at")
        await self._reports.create_index("task_id")

    async def create_task(self, payload: DeployTaskCreate) -> DeployTask:
        document = payload.to_document()
        await self._tasks.insert_one(document)
        return DeployTask.from_mongo(document)

    async def get_task(self, task_id: str) -> Optional[DeployTask]:
        document = await self._tasks.find_one({"_id": task_id})
        if not document:
            return None
        return DeployTask.from_mongo(document)

    async def update_task(self, task_id: str, update: DeployTaskUpdate) -> Optional[DeployTask]:
        update_query = update.to_update_query()
        if not update_query:
            return await self.get_task(task_id)

        document = await self._tasks.find_one_and_update(
            {"_id": task_id},
            update_query,
            return_document=ReturnDocument.AFTER,
        )
        if not document:
            return None
        return DeployTask.from_mongo(document)

    async def mark_status(
        self, task_id: str, status: DeployStatus, *, error_log: Optional[str] = None
    ) -> Optional[DeployTask]:
        update = DeployTaskUpdate(status=status, error_log=error_log)
        if status in (DeployStatus.COMPLETED, DeployStatus.FAILED):
            update.completed_at = datetime.now(timezone.utc)
        return await self.update_task(task_id, update)

    async def insert_report(self, report: DeployReport) -> DeployReport:
        document = report.to_mongo()
        await self._reports.insert_one(document)
        return DeployReport.from_mongo(document)

    async def get_report(self, report_id: str) -> Optional[DeployReport]:
        document = await self._reports.find_one({"_id": report_id})
        if not document:
            return None
        return DeployReport.from_mongo(document)
