from __future__ import annotations

import asyncio
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from domain import DeployStatus, is_valid_transition
from models import DeployTask, DeployTaskCreate, DeployTaskUpdate, utc_now
from repositories import DeployTaskRepository
from settings import Settings


logger = logging.getLogger("cherry-deploy.deploy")


class DeployService:
    """Coordinates deploy task lifecycle and orchestrates pipeline execution."""

    def __init__(self, repository: DeployTaskRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.dry_run = settings.deploy_dry_run
        self.chatbot_repo_path = Path(settings.chatbot_repo_path)
        self.nginx_green_path = Path(settings.nginx_green_path)
        self.nginx_blue_path = Path(settings.nginx_blue_path)
        self.nginx_live_symlink = Path(settings.nginx_live_symlink)
        self.default_branch = settings.deploy_default_branch.strip()
        self.allowed_branches = {
            branch.strip()
            for branch in settings.deploy_allowed_branches.split(",")
            if branch.strip()
        } or {self.default_branch}
        logger.info(
            "DeployService initialized (dry_run=%s, default_branch=%s, allowed_branches=%s)",
            self.dry_run,
            self.default_branch,
            sorted(self.allowed_branches),
        )

    async def create_task(self, *, branch: str) -> DeployTask:
        branch = (branch or self.default_branch).strip()
        if branch not in self.allowed_branches:
            raise ValueError(
                f"Branch '{branch}' is not allowed. Allowed branches: {sorted(self.allowed_branches)}"
            )
        task_id = uuid4().hex
        task = await self.repository.create_task(
            DeployTaskCreate(
                task_id=task_id,
                metadata={"branch": branch},
            )
        )
        return task

    async def get_task(self, task_id: str) -> DeployTask:
        task = await self.repository.get_task(task_id)
        if not task:
            raise RuntimeError(f"deploy task not found: {task_id}")
        return task

    async def run_pipeline(self, task_id: str, branch: str) -> None:
        logger.info("Starting deploy pipeline task=%s branch=%s", task_id, branch)
        try:
            await self._ensure_valid_transition(task_id, DeployStatus.RUNNING_CLONE)
            clone_metadata = await self._run_clone_stage(branch)
            await self._append_stage_metadata(task_id, DeployStatus.RUNNING_CLONE, clone_metadata)

            await self._ensure_valid_transition(task_id, DeployStatus.RUNNING_BUILD)
            build_metadata = await self._run_build_stage()
            await self._append_stage_metadata(task_id, DeployStatus.RUNNING_BUILD, build_metadata)

            await self._ensure_valid_transition(task_id, DeployStatus.RUNNING_CUTOVER)
            cutover_metadata = await self._run_cutover_stage()
            await self._append_stage_metadata(task_id, DeployStatus.RUNNING_CUTOVER, cutover_metadata)

            await self._ensure_valid_transition(task_id, DeployStatus.RUNNING_OBSERVABILITY)
            observability_metadata = await self._run_observability_stage()
            await self._append_stage_metadata(
                task_id,
                DeployStatus.RUNNING_OBSERVABILITY,
                observability_metadata,
            )

            await self.repository.mark_status(task_id, DeployStatus.COMPLETED)
            await self.repository.update_task(
                task_id,
                DeployTaskUpdate(
                    append_metadata={
                        "summary": {
                            "completed_at": utc_now().isoformat(),
                            "result": "success",
                        }
                    }
                ),
            )
            logger.info("Deploy pipeline succeeded task=%s", task_id)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Deploy pipeline failed task=%s error=%s", task_id, exc)
            await self.repository.mark_status(
                task_id,
                DeployStatus.FAILED,
                error_log=str(exc),
            )

    async def _ensure_valid_transition(self, task_id: str, new_status: DeployStatus) -> None:
        document = await self.repository.get_task(task_id)
        if not document:
            raise RuntimeError(f"deploy task not found: {task_id}")
        if not is_valid_transition(document.status, new_status):
            raise RuntimeError(
                f"invalid status transition from {document.status} to {new_status}"
            )
        await self.repository.update_task(
            task_id,
            DeployTaskUpdate(
                status=new_status,
                append_metadata={
                    new_status.value: {"timestamp": utc_now().isoformat()}
                },
            ),
        )

    async def _append_stage_metadata(
        self,
        task_id: str,
        status: DeployStatus,
        metadata: Dict[str, Any],
    ) -> None:
        await self.repository.update_task(
            task_id,
            DeployTaskUpdate(
                append_metadata={status.value: metadata},
            ),
        )

    async def _run_clone_stage(self, branch: str) -> Dict[str, Any]:
        steps: list[Dict[str, Any]] = []

        commands = [
            (["git", "fetch", "origin"], "Fetch latest refs from origin"),
            (
                ["git", "checkout", "-B", branch, f"origin/{branch}"],
                "Checkout deploy branch aligned with origin",
            ),
            (
                ["git", "reset", "--hard", f"origin/{branch}"],
                "Hard reset working tree to origin/branch",
            ),
            (["git", "clean", "-fdx"], "Remove untracked files (full replace)"),
        ]

        for cmd, description in commands:
            steps.append(
                await self._run_command(
                    cmd,
                    cwd=self.chatbot_repo_path,
                    description=description,
                )
            )

        return {"branch": branch, "steps": steps}

    async def _run_build_stage(self) -> Dict[str, Any]:
        command = ["npm", "run", "build"]
        return await self._run_command(
            command,
            cwd=self.chatbot_repo_path,
            description="Build frontend artifacts",
        )

    async def _run_cutover_stage(self) -> Dict[str, Any]:
        build_dir = self.chatbot_repo_path / "build"
        metadata: Dict[str, Any] = {
            "source": str(build_dir),
            "green_target": str(self.nginx_green_path),
            "live_symlink": str(self.nginx_live_symlink),
        }
        if self.dry_run:
            metadata["dry_run"] = True
            return metadata

        if not build_dir.exists():
            raise RuntimeError(f"build directory missing: {build_dir}")

        self.nginx_green_path.parent.mkdir(parents=True, exist_ok=True)
        if self.nginx_green_path.exists():
            shutil.rmtree(self.nginx_green_path)
        shutil.copytree(build_dir, self.nginx_green_path)

        if self.nginx_live_symlink.exists() or self.nginx_live_symlink.is_symlink():
            self.nginx_live_symlink.unlink()
        self.nginx_live_symlink.symlink_to(self.nginx_green_path, target_is_directory=True)

        metadata["dry_run"] = False
        metadata["copied"] = True
        return metadata

    async def _run_observability_stage(self) -> Dict[str, Any]:
        # Placeholder for future Lighthouse or monitoring integrations.
        return {
            "message": "Observability checks are not implemented yet.",
            "dry_run": self.dry_run,
        }

    async def get_preview(self) -> Dict[str, Any]:
        """Return a static preview payload with risk/cost notes for the deploy command."""
        return {
            "current_branch": self.default_branch,
            "target_repo": str(self.chatbot_repo_path),
            "commands": [
                "git fetch origin",
                f"git checkout -B {self.default_branch} origin/{self.default_branch}",
                f"git reset --hard origin/{self.default_branch}",
                "git clean -fdx",
                "npm run build",
                "sync static assets to nginx green path",
            ],
            "risk_assessment": {
                "downtime": "Minimal (blue/green swap)",
                "rollback": "Sym-link revert to previous blue directory",
                "observability": "Manual Lighthouse check pending automation",
            },
            "cost_estimate": {
                "runtime_minutes": 8,
                "npm_dependencies": "No extra cost",
                "lighthouse_tokens": "N/A",
            },
        }

    async def _run_command(
        self,
        command: list[str],
        *,
        cwd: Optional[Path] = None,
        description: str,
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "description": description,
            "command": " ".join(command),
            "cwd": str(cwd) if cwd else None,
        }

        if self.dry_run:
            metadata["dry_run"] = True
            return metadata

        if cwd and not cwd.exists():
            raise RuntimeError(f"command working directory missing: {cwd}")

        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(cwd) if cwd else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()

        metadata["stdout"] = stdout_bytes.decode().strip()
        metadata["stderr"] = stderr_bytes.decode().strip()
        metadata["returncode"] = process.returncode

        if process.returncode != 0:
            raise RuntimeError(
                f"command failed ({metadata['command']}): {metadata['stderr'] or metadata['stdout']}"
            )

        return metadata
