from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_CODE_PATH = PROJECT_ROOT / "api-code"
if str(API_CODE_PATH) not in sys.path:
    sys.path.insert(0, str(API_CODE_PATH))

from domain import DeployStatus
from models import DeployTask, DeployTaskCreate, DeployTaskUpdate, utc_now
from schemas import DeployRequest
from services import DeployService
from settings import Settings


class InMemoryDeployTaskRepository:
    def __init__(self) -> None:
        self.tasks: dict[str, DeployTask] = {}

    async def ensure_indexes(self) -> None:  # pragma: no cover - not used in tests
        return

    async def create_task(self, payload: DeployTaskCreate) -> DeployTask:
        task = DeployTask.from_mongo(payload.to_document())
        self.tasks[task.task_id] = task
        return task

    async def get_task(self, task_id: str) -> DeployTask | None:
        return self.tasks.get(task_id)

    async def update_task(
        self,
        task_id: str,
        update: DeployTaskUpdate,
    ) -> DeployTask | None:
        task = self.tasks.get(task_id)
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
        self.tasks[task_id] = task
        return task

    async def mark_status(
        self,
        task_id: str,
        status: DeployStatus,
        *,
        error_log: str | None = None,
    ) -> DeployTask | None:
        task = self.tasks.get(task_id)
        if not task:
            return None
        task.status = status
        if error_log:
            task.error_log = error_log
        if status in (DeployStatus.COMPLETED, DeployStatus.FAILED):
            task.completed_at = utc_now()
        self.tasks[task_id] = task
        return task


class DeployServiceTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:  # noqa: N802
        self.repository = InMemoryDeployTaskRepository()
        self.settings = Settings.model_validate(
            {
                "GEMINI_API_KEY": None,
                "MONGODB_URI": "mongodb://localhost:27017",
                "MONGODB_DB_NAME": "test",
                "CHATBOT_REPO_PATH": ".",
                "NGINX_GREEN_PATH": "./green",
                "NGINX_BLUE_PATH": "./blue",
                "NGINX_LIVE_SYMLINK": "./current",
                "DEPLOY_DRY_RUN": True,
            }
        )
        self.service = DeployService(self.repository, self.settings)

    async def test_deploy_pipeline_completes_in_dry_run(self) -> None:
        request = DeployRequest(branch="deploy")
        task = await self.service.create_task(branch=request.branch or "")

        await self.service.run_pipeline(task.task_id, request.branch or "")

        stored = await self.repository.get_task(task.task_id)
        self.assertIsNotNone(stored)
        assert stored is not None
        self.assertEqual(stored.status, DeployStatus.COMPLETED)
        self.assertEqual(stored.metadata.get("branch"), "deploy")

        clone_meta = stored.metadata[DeployStatus.RUNNING_CLONE.value]
        self.assertEqual(clone_meta.get("branch"), "deploy")
        self.assertTrue(clone_meta.get("steps"))
        for step in clone_meta["steps"]:
            self.assertTrue(step.get("dry_run"))

        for stage in (
            DeployStatus.RUNNING_BUILD,
            DeployStatus.RUNNING_CUTOVER,
            DeployStatus.RUNNING_OBSERVABILITY,
        ):
            self.assertIn(stage.value, stored.metadata)
            self.assertIn("dry_run", stored.metadata[stage.value])
        self.assertIn("summary", stored.metadata)
        self.assertEqual(stored.metadata["summary"]["result"], "success")

    async def test_get_task_returns_document(self) -> None:
        request = DeployRequest(branch="main")
        task = await self.service.create_task(branch=request.branch or "")

        fetched = await self.service.get_task(task.task_id)
        self.assertEqual(fetched.task_id, task.task_id)

    async def test_create_task_rejects_unknown_branch(self) -> None:
        with self.assertRaises(ValueError):
            await self.service.create_task(branch="feature/experimental")

    async def test_get_task_missing_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            await self.service.get_task("missing")


def _merge_metadata(base: dict, extra: dict) -> None:
    for key, value in extra.items():
        if isinstance(value, dict):
            child = base.setdefault(key, {})
            _merge_metadata(child, value)
        else:
            base[key] = value


if __name__ == "__main__":
    unittest.main()
