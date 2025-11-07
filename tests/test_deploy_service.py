from __future__ import annotations

import asyncio
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

    async def get_recent_successes(self, branch: str, limit: int = 2) -> list[DeployTask]:
        successes = [
            task
            for task in self.tasks.values()
            if task.status == DeployStatus.COMPLETED and task.metadata.get("branch") == branch
        ]
        successes.sort(key=lambda t: t.completed_at or utc_now(), reverse=True)
        return successes[:limit]


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
        summary = stored.metadata["summary"]
        self.assertEqual(summary["result"], "success")
        self.assertIn("preflight", summary)
        preflight = summary["preflight"]
        self.assertIn("cost_estimate", preflight)
        self.assertIn("risk_assessment", preflight)
        self.assertIn("llm_preview", preflight)
        self.assertIn("summary", preflight["llm_preview"])

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

    async def test_prepare_and_perform_rollback(self) -> None:
        # seed two successful deploy records
        oldest = await self.repository.create_task(
            DeployTaskCreate(task_id="oldest", metadata={"branch": "deploy"})
        )
        await self.repository.update_task(
            oldest.task_id,
            DeployTaskUpdate(
                status=DeployStatus.COMPLETED,
                completed_at=utc_now(),
                append_metadata={
                    "summary": {
                        "result": "success",
                        "commit": "commit-oldest",
                        "completed_at": utc_now().isoformat(),
                    }
                },
            ),
        )

        latest = await self.repository.create_task(
            DeployTaskCreate(task_id="latest", metadata={"branch": "deploy"})
        )
        await self.repository.update_task(
            latest.task_id,
            DeployTaskUpdate(
                status=DeployStatus.COMPLETED,
                completed_at=utc_now(),
                append_metadata={
                    "summary": {
                        "result": "success",
                        "commit": "commit-latest",
                        "completed_at": utc_now().isoformat(),
                    }
                },
            ),
        )

        task, target_commit, current_commit, branch = await self.service.prepare_rollback("deploy")
        self.assertEqual(branch, "deploy")
        self.assertEqual(target_commit, "commit-oldest")
        self.assertEqual(current_commit, "commit-latest")

        await self.service.perform_rollback(task.task_id, branch, target_commit, current_commit)

        stored = await self.repository.get_task(task.task_id)
        assert stored is not None
        self.assertEqual(stored.status, DeployStatus.COMPLETED)
        summary = stored.metadata.get("summary", {})
        self.assertEqual(summary.get("rolled_back_from"), "commit-latest")
        self.assertEqual(summary.get("rolled_back_to"), "commit-oldest")

    async def test_prepare_rollback_requires_history(self) -> None:
        only = await self.repository.create_task(
            DeployTaskCreate(task_id="only", metadata={"branch": "deploy"})
        )
        await self.repository.update_task(
            only.task_id,
            DeployTaskUpdate(
                status=DeployStatus.COMPLETED,
                completed_at=utc_now(),
                append_metadata={
                    "summary": {
                        "result": "success",
                        "commit": "commit-only",
                        "completed_at": utc_now().isoformat(),
                    }
                },
            ),
        )
        with self.assertRaises(RuntimeError):
            await self.service.prepare_rollback("deploy")

    async def test_describe_blue_green_state_defaults_in_dev_mode(self) -> None:
        state = await self.service.describe_blue_green_state()
        self.assertEqual(state["active_slot"], "unknown")
        self.assertEqual(state["next_cutover_target"], "dev-server")
        self.assertIsNone(state["standby_slot"])

    async def test_run_pipeline_serializes_concurrent_invocations(self) -> None:
        request = DeployRequest(branch="deploy")
        first = await self.service.create_task(branch=request.branch or "")
        second = await self.service.create_task(branch=request.branch or "")

        original_run_command = self.service._run_command

        async def fake_run_command(command, *, cwd=None, description):  # type: ignore[override]
            await asyncio.sleep(0.01)
            return {
                "description": description,
                "command": " ".join(command),
                "cwd": str(cwd) if cwd else None,
                "dry_run": True,
            }

        self.service._run_command = fake_run_command  # type: ignore[assignment]

        order: list[str] = []

        async def invoke(task_id: str, label: str) -> None:
            order.append(f"{label}_start")
            await self.service.run_pipeline(task_id, request.branch or "")
            order.append(f"{label}_end")

        try:
            await asyncio.gather(
                invoke(first.task_id, "t1"),
                invoke(second.task_id, "t2"),
            )
        finally:
            self.service._run_command = original_run_command  # type: ignore[assignment]

        self.assertEqual(order, ["t1_start", "t2_start", "t1_end", "t2_end"])

        stored_first = await self.repository.get_task(first.task_id)
        stored_second = await self.repository.get_task(second.task_id)
        assert stored_first is not None
        assert stored_second is not None
        self.assertEqual(stored_first.status, DeployStatus.COMPLETED)
        self.assertEqual(stored_second.status, DeployStatus.COMPLETED)


    async def test_cutover_metadata_cycles_between_targets(self) -> None:
        self.service.frontend_build_output_path = Path("./fake_build")
        live_symlink = self.service.nginx_live_symlink
        if live_symlink.exists() or live_symlink.is_symlink():
            live_symlink.unlink()
        live_symlink.symlink_to(self.service.nginx_green_path, target_is_directory=True)
        self.addCleanup(lambda: live_symlink.unlink(missing_ok=True))

        request = DeployRequest(branch="deploy")
        task = await self.service.create_task(branch=request.branch or "")
        await self.service.run_pipeline(task.task_id, request.branch or "")

        stored = await self.repository.get_task(task.task_id)
        assert stored is not None
        cutover_meta = stored.metadata[DeployStatus.RUNNING_CUTOVER.value]
        self.assertEqual(
            cutover_meta["next_target"],
            str(self.service.nginx_blue_path.resolve()),
        )
        self.assertEqual(
            cutover_meta["previous_target"],
            str(self.service.nginx_green_path.resolve()),
        )
        self.assertTrue(cutover_meta["dry_run"])

def _merge_metadata(base: dict, extra: dict) -> None:
    for key, value in extra.items():
        if isinstance(value, dict):
            child = base.setdefault(key, {})
            _merge_metadata(child, value)
        else:
            base[key] = value


if __name__ == "__main__":
    unittest.main()
