from __future__ import annotations

from collections import defaultdict
from typing import Dict, Optional

from domain import DeployStatus
from models import DeployReport, DeployTask, DeployTaskCreate, DeployTaskUpdate, utc_now


class InMemoryDeployTaskRepository:
    """Fallback repository used when MongoDB is unavailable."""

    def __init__(self) -> None:
        self._tasks: Dict[str, DeployTask] = {}
        self._reports: Dict[str, DeployReport] = {}

    async def ensure_indexes(self) -> None:  # pragma: no cover - no-op
        return

    async def create_task(self, payload: DeployTaskCreate) -> DeployTask:
        document = payload.to_document()
        task = DeployTask.from_mongo(document)
        self._tasks[task.task_id] = task
        return task

    async def get_task(self, task_id: str) -> Optional[DeployTask]:
        return self._tasks.get(task_id)

    async def update_task(self, task_id: str, update: DeployTaskUpdate) -> Optional[DeployTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None

        if update.status is not None:
            task.status = update.status
        if update.error_log is not None:
            task.error_log = update.error_log
        if update.completed_at is not None:
            task.completed_at = update.completed_at
        if update.metadata:
            task.metadata = update.metadata
        if update.append_metadata:
            _merge_metadata(task.metadata, update.append_metadata)

        self._tasks[task_id] = task
        return task

    async def mark_status(
        self,
        task_id: str,
        status: DeployStatus,
        *,
        error_log: Optional[str] = None,
    ) -> Optional[DeployTask]:
        task = self._tasks.get(task_id)
        if not task:
            return None
        task.status = status
        if error_log:
            task.error_log = error_log
        if status in (DeployStatus.COMPLETED, DeployStatus.FAILED):
            task.completed_at = utc_now()
        self._tasks[task_id] = task
        return task

    async def insert_report(self, report: DeployReport) -> DeployReport:
        self._reports[report.report_id] = report
        return report

    async def get_report(self, report_id: str) -> Optional[DeployReport]:
        return self._reports.get(report_id)


def _merge_metadata(base: dict, extra: dict) -> None:
    for key, value in extra.items():
        if isinstance(value, dict):
            child = base.setdefault(key, {})
            _merge_metadata(child, value)
        else:
            base[key] = value
