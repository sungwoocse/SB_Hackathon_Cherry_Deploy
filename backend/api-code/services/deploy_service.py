from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import getpass
import json
from urllib import error as urllib_error, parse as urllib_parse, request as urllib_request
from zoneinfo import ZoneInfo

import google.generativeai as genai

from domain import DeployStatus, is_valid_transition
from models import DeployTask, DeployTaskCreate, DeployTaskUpdate, utc_now
from repositories import DeployTaskRepository
from settings import Settings


logger = logging.getLogger("cherry-deploy.deploy")

STAGE_SEQUENCE: List[str] = [
    DeployStatus.RUNNING_CLONE.value,
    DeployStatus.RUNNING_BUILD.value,
    DeployStatus.RUNNING_CUTOVER.value,
    DeployStatus.RUNNING_OBSERVABILITY.value,
]

STAGE_LABELS: Dict[str, str] = {
    DeployStatus.RUNNING_CLONE.value: "Git sync & checkout",
    DeployStatus.RUNNING_BUILD.value: "Install & build frontend",
    DeployStatus.RUNNING_CUTOVER.value: "Blue/Green cutover",
    DeployStatus.RUNNING_OBSERVABILITY.value: "Observability checks",
}

STAGE_DEFAULT_SECONDS: Dict[str, int] = {
    DeployStatus.RUNNING_CLONE.value: 35,
    DeployStatus.RUNNING_BUILD.value: 90,
    DeployStatus.RUNNING_CUTOVER.value: 25,
    DeployStatus.RUNNING_OBSERVABILITY.value: 20,
}

STAGE_PLAN_DESCRIPTIONS: Dict[str, str] = {
    DeployStatus.RUNNING_CLONE.value: "Fetch latest refs, reset branch, and ensure a clean working tree.",
    DeployStatus.RUNNING_BUILD.value: "Install npm packages and produce production-ready Next.js artifacts.",
    DeployStatus.RUNNING_CUTOVER.value: "Sync exported assets to the standby color and flip the Nginx symlink.",
    DeployStatus.RUNNING_OBSERVABILITY.value: "Run smoke checks and verify PM2/nginx health before closing the task.",
}

ESTIMATED_DEPLOY_HOURLY_COST = 6.0  # rough EC2/engineer blended cost per hour (USD)
COMMIT_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class AsyncReentrantLock:
    """Minimal re-entrant asyncio lock used to serialize deploy pipelines."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._owner: Optional[asyncio.Task[Any]] = None
        self._depth = 0

    async def acquire(self) -> None:
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("AsyncReentrantLock requires a running task.")
        if self._owner is current:
            self._depth += 1
            return
        await self._lock.acquire()
        self._owner = current
        self._depth = 1

    def release(self) -> None:
        current = asyncio.current_task()
        if current is None or self._owner is not current:
            raise RuntimeError("AsyncReentrantLock released by non-owner task.")
        self._depth -= 1
        if self._depth == 0:
            self._owner = None
            self._lock.release()

    async def __aenter__(self) -> "AsyncReentrantLock":
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[override]
        self.release()


class CommandExecutionError(RuntimeError):
    """Raised when a subprocess command fails."""

    def __init__(
        self,
        command: list[str],
        cwd: Optional[Path],
        returncode: int,
        stdout: str,
        stderr: str,
    ) -> None:
        self.command = command
        self.cwd = cwd
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        message = stderr or stdout or f"return code {returncode}"
        super().__init__(f"command failed ({' '.join(command)}): {message}")


class DeployService:
    """Coordinates deploy task lifecycle and orchestrates pipeline execution."""

    def __init__(self, repository: DeployTaskRepository, settings: Settings):
        self.repository = repository
        self.settings = settings
        self.dry_run = settings.deploy_dry_run
        self.chatbot_repo_path = Path(settings.chatbot_repo_path)
        self.frontend_project_path = self._resolve_frontend_path(settings.frontend_project_subdir)
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

        self.frontend_install_command = self._parse_command(settings.frontend_install_command)
        self.frontend_build_command = self._parse_command(settings.frontend_build_command)
        export_cmd = (settings.frontend_export_command or "").strip()
        self.frontend_export_command = self._parse_command(export_cmd) if export_cmd else None
        self.frontend_build_output_path = self._resolve_output_path(
            settings.frontend_build_output_subdir
        )
        self.dev_server_mode = self.frontend_build_output_path is None
        self.preview_use_github_compare = settings.preview_use_github_compare
        self.github_compare_repo = (settings.github_compare_repo or "").strip()
        self.github_compare_head_ref = (settings.github_compare_head_ref or "").strip()
        self.github_compare_token = (settings.github_compare_token or "").strip() or None
        self.github_compare_cache_seconds = max(0, int(settings.github_compare_cache_seconds or 0))
        self._compare_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._pipeline_lock = AsyncReentrantLock()
        if self.preview_use_github_compare and not self.github_compare_repo:
            logger.warning(
                "PREVIEW_USE_GITHUB_COMPARE is enabled but GITHUB_COMPARE_REPO is not configured; "
                "falling back to local git diff."
            )
        try:
            self.display_timezone = ZoneInfo(settings.display_timezone)
            self.display_timezone_name = settings.display_timezone
        except Exception:  # pragma: no cover - fallback to UTC if timezone missing
            self.display_timezone = ZoneInfo("UTC")
            self.display_timezone_name = "UTC"

    def _resolve_frontend_path(self, subdir: str) -> Path:
        subdir = (subdir or "").strip()
        candidate = Path(subdir)
        if candidate.is_absolute():
            return candidate
        return (self.chatbot_repo_path / candidate).resolve()

    def _resolve_output_path(self, subdir: str) -> Optional[Path]:
        subdir = (subdir or "").strip()
        if not subdir:
            return None
        candidate = Path(subdir)
        if candidate.is_absolute():
            return candidate
        return (self.frontend_project_path / candidate).resolve()

    @staticmethod
    def _parse_command(command: str) -> list[str]:
        command = (command or "").strip()
        if not command:
            return []
        return shlex.split(command)

    @staticmethod
    def _looks_like_commit(value: Optional[str]) -> bool:
        return bool(value and COMMIT_SHA_PATTERN.match(value))

    def _extract_stage_snapshots(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        snapshots: Dict[str, Any] = {}
        for key in STAGE_SEQUENCE:
            if key in metadata:
                snapshots[key] = metadata[key]
        return snapshots

    def build_stage_snapshot(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Expose stage data for routers/consumers."""
        return self._extract_stage_snapshots(metadata)

    def _build_timeline_from_stage_data(
        self,
        stage_seconds: Dict[str, int],
        stage_snapshots: Dict[str, Any],
    ) -> list[Dict[str, Any]]:
        timeline: list[Dict[str, Any]] = []
        active_found = False
        for key in STAGE_SEQUENCE:
            snapshot = stage_snapshots.get(key) or {}
            metadata = self._build_stage_metadata_template(key, stage_seconds)
            if isinstance(snapshot, dict):
                merged = dict(snapshot)
                metadata.update({k: v for k, v in merged.items() if v is not None})
            status = self._derive_stage_status(key, stage_snapshots, active_found)
            if status == "upcoming" and not active_found:
                active_found = True
            timeline.append(
                {
                    "stage": key,
                    "label": STAGE_LABELS.get(key, key),
                    "expected_seconds": stage_seconds.get(key),
                    "completed": key in stage_snapshots,
                    "status": status,
                    "metadata": metadata,
                }
            )
        return timeline

    def _build_estimated_timeline(self, stage_seconds: Dict[str, int]) -> list[Dict[str, Any]]:
        timeline: list[Dict[str, Any]] = []
        for index, key in enumerate(STAGE_SEQUENCE):
            metadata = self._build_stage_metadata_template(key, stage_seconds)
            timeline.append(
                {
                    "stage": key,
                    "label": STAGE_LABELS.get(key, key),
                    "expected_seconds": stage_seconds.get(key),
                    "completed": False,
                    "status": "upcoming" if index == 0 else "pending",
                    "metadata": metadata,
                }
            )
        return timeline

    def _derive_stage_status(
        self,
        stage: str,
        stage_snapshots: Dict[str, Any],
        active_found: bool,
    ) -> str:
        if stage in stage_snapshots:
            return "completed"
        if not active_found:
            return "upcoming"
        return "pending"

    def _build_stage_metadata_template(
        self, stage: str, stage_seconds: Dict[str, int]
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "plan": STAGE_PLAN_DESCRIPTIONS.get(stage, stage),
            "eta_seconds": stage_seconds.get(stage),
        }
        if stage == DeployStatus.RUNNING_CLONE.value:
            metadata["checks"] = ["git fetch origin", "hard reset to remote", "clean working tree"]
        elif stage == DeployStatus.RUNNING_BUILD.value:
            metadata["checks"] = ["npm install", "npm run build", "npm run export"]
        elif stage == DeployStatus.RUNNING_CUTOVER.value:
            metadata["checks"] = [
                "sync export to standby color",
                "flip /var/www/.../current symlink",
                "reload nginx (systemd)",
            ]
        elif stage == DeployStatus.RUNNING_OBSERVABILITY.value:
            metadata["checks"] = ["pm2 status main-api/frontend-dev", "curl /healthz"]
        return metadata

    def _estimate_stage_seconds(self, diff_stats: Dict[str, Any]) -> Dict[str, int]:
        file_count = diff_stats.get("file_count", 0)
        lockfile = diff_stats.get("lockfile_changed", False)
        config = diff_stats.get("config_changed", False)

        clone_seconds = STAGE_DEFAULT_SECONDS[DeployStatus.RUNNING_CLONE.value] + min(20, file_count)

        build_seconds = STAGE_DEFAULT_SECONDS[DeployStatus.RUNNING_BUILD.value] + file_count * 5
        if lockfile:
            build_seconds += 45
        if config:
            build_seconds += 15
        build_seconds = min(build_seconds, 420)

        cutover_seconds = STAGE_DEFAULT_SECONDS[DeployStatus.RUNNING_CUTOVER.value]
        observability_seconds = STAGE_DEFAULT_SECONDS[DeployStatus.RUNNING_OBSERVABILITY.value]

        return {
            DeployStatus.RUNNING_CLONE.value: clone_seconds,
            DeployStatus.RUNNING_BUILD.value: build_seconds,
            DeployStatus.RUNNING_CUTOVER.value: cutover_seconds,
            DeployStatus.RUNNING_OBSERVABILITY.value: observability_seconds,
        }

    @staticmethod
    def _estimate_cost_summary(stage_seconds: Dict[str, int], diff_stats: Dict[str, Any]) -> Dict[str, Any]:
        total_seconds = sum(stage_seconds.values())
        runtime_minutes = max(1, round(total_seconds / 60))
        hourly_cost = round((total_seconds / 3600) * ESTIMATED_DEPLOY_HOURLY_COST, 2)
        return {
            "runtime_minutes": runtime_minutes,
            "hourly_cost": hourly_cost,
            "inputs": {
                "files_changed": diff_stats.get("file_count", 0),
                "lockfile_changed": diff_stats.get("lockfile_changed", False),
            },
        }

    def _build_risk_assessment(self, diff_stats: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        risk_level = diff_stats.get("risk_level", "unknown")
        return {
            "risk_level": risk_level,
            "files_changed": diff_stats.get("file_count", 0),
            "downtime": "Minimal (Nginx keeps previous color live during cutover)",
            "rollback": "Symlink swap to previous color remains available",
            "notes": list(dict.fromkeys(warnings)),
        }

    def _build_preview_warnings(
        self, diff_stats: Dict[str, Any], diff_context: Dict[str, Any]
    ) -> List[str]:
        warnings = list(diff_stats.get("warnings", []))
        if diff_stats.get("sensitive_changed"):
            warnings.append("Sensitive files (certs/keys/secrets) changed; audit secrets rotation.")
        if diff_stats.get("test_files_changed"):
            warnings.append("Test files changed; ensure npm test passes before cutover.")
        if diff_stats.get("file_count", 0) == 0:
            warnings.append("No file changes detected; confirm deploy is necessary.")
        if not diff_context.get("ready") and diff_context.get("reason"):
            warnings.append(str(diff_context["reason"]))
        warnings.append("Automated tests are not run by this pipeline; execute npm run lint && npm test manually.")
        warnings.append(
            "Observability relies on manual health checks; monitor /healthz and PM2 logs after cutover."
        )
        warnings = [msg for msg in warnings if msg]
        return list(dict.fromkeys(warnings))

    async def _prepare_preview_inputs(
        self,
    ) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, int], List[str], Dict[str, Any]]:
        diff_context = await self._resolve_preview_context()
        diff_stats = diff_context.get("diff_stats", {})
        stage_seconds = self._estimate_stage_seconds(diff_stats)
        warnings = self._build_preview_warnings(diff_stats, diff_context)
        cost_estimate = self._estimate_cost_summary(stage_seconds, diff_stats)
        return diff_context, diff_stats, stage_seconds, warnings, cost_estimate

    def _assemble_task_context(self, task: DeployTask) -> Dict[str, Any]:
        metadata = task.metadata or {}
        context: Dict[str, Any] = {
            "task_id": task.task_id,
            "status": task.status,
            "branch": metadata.get("branch", self.default_branch),
            "action": metadata.get("action", "deploy"),
            "started_at": self._to_display_time(task.started_at),
            "completed_at": self._to_display_time(task.completed_at),
            "timezone": self.display_timezone_name,
        }
        summary = metadata.get("summary")
        if isinstance(summary, dict):
            context["summary"] = summary
        failure_context = metadata.get("failure_context")
        if failure_context:
            context["failure_context"] = failure_context
        actor = metadata.get("actor") or metadata.get("requested_by")
        if actor:
            context["actor"] = actor
        return context

    async def create_task(self, *, branch: str) -> DeployTask:
        branch = (branch or self.default_branch).strip()
        if branch not in self.allowed_branches:
            raise ValueError(
                f"Branch '{branch}' is not allowed. Allowed branches: {sorted(self.allowed_branches)}"
            )
        task_id = uuid4().hex
        metadata: Dict[str, Any] = {
            "branch": branch,
            "action": "deploy",
        }
        metadata = self._attach_actor_metadata(metadata)
        task = await self.repository.create_task(
            DeployTaskCreate(
                task_id=task_id,
                metadata=metadata,
            )
        )
        return task

    async def prepare_rollback(
        self, branch: Optional[str] = None
    ) -> tuple[DeployTask, str, Optional[str], str]:
        branch = (branch or self.default_branch).strip()
        if branch not in self.allowed_branches:
            raise ValueError(
                f"Branch '{branch}' is not allowed. Allowed branches: {sorted(self.allowed_branches)}"
            )

        recent = await self.repository.get_recent_successes(branch=branch, limit=2)
        if len(recent) < 2:
            error = "Not enough successful deployments to rollback."
            logger.warning(error)
            raise RuntimeError(error)

        current, target = recent[0], recent[1]
        current_commit = (
            current.metadata.get("summary", {}).get("commit")
            if isinstance(current.metadata.get("summary"), dict)
            else None
        )
        target_commit = (
            target.metadata.get("summary", {}).get("commit")
            if isinstance(target.metadata.get("summary"), dict)
            else None
        )

        if not target_commit:
            raise RuntimeError("Target commit for rollback is unknown.")

        task = await self.repository.create_task(
            DeployTaskCreate(
                task_id=uuid4().hex,
                metadata=self._attach_actor_metadata(
                    {
                        "branch": branch,
                        "action": "rollback",
                        "from_commit": current_commit,
                        "to_commit": target_commit,
                    }
                ),
            )
        )

        return task, target_commit, current_commit, branch

    async def perform_rollback(
        self,
        task_id: str,
        branch: str,
        target_commit: str,
        current_commit: Optional[str],
    ) -> None:
        await self.run_pipeline(
            task_id,
            branch,
            target_commit=target_commit,
            force_push=not self.dry_run,
        )
        if current_commit:
            await self.repository.update_task(
                task_id,
                DeployTaskUpdate(
                    append_metadata={
                        "summary": {
                            "rolled_back_from": current_commit,
                            "rolled_back_to": target_commit,
                        }
                    }
                ),
            )

    async def rollback(self, branch: Optional[str] = None) -> DeployTask:
        task, target_commit, current_commit, branch_value = await self.prepare_rollback(branch)
        await self.perform_rollback(
            task.task_id,
            branch_value,
            target_commit,
            current_commit,
        )
        updated = await self.repository.get_task(task.task_id)
        if not updated:
            raise RuntimeError("Rollback task not found after execution.")
        return updated

    async def get_task(self, task_id: str) -> DeployTask:
        task = await self.repository.get_task(task_id)
        if not task:
            raise RuntimeError(f"deploy task not found: {task_id}")
        return task

    async def run_pipeline(
        self,
        task_id: str,
        branch: str,
        *,
        target_commit: Optional[str] = None,
        force_push: bool = False,
    ) -> None:
        async with self._pipeline_lock:
            logger.info(
                "Starting deploy pipeline task=%s branch=%s target_commit=%s force_push=%s",
                task_id,
                branch,
                target_commit,
                force_push,
            )
            task_document = await self.repository.get_task(task_id)
            action = (task_document.metadata.get("action") if task_document else None) or "deploy"
            auto_recovery: Optional[Dict[str, Any]] = None
            try:
                await self._prime_preflight_metadata(task_id)
            except Exception as snapshot_exc:  # pragma: no cover - diagnostic only
                logger.warning(
                    "Unable to cache preflight snapshot for task=%s (%s)",
                    task_id,
                    snapshot_exc,
                )

            try:
                await self._ensure_valid_transition(task_id, DeployStatus.RUNNING_CLONE)
                clone_metadata = await self._run_clone_stage(
                    branch,
                    target_commit=target_commit,
                    force_push=force_push,
                )
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
                summary_commit = await self._get_current_commit()
                commit_details = await self._get_commit_details()
                actor_identity = self._resolve_actor_identity()
                await self.repository.update_task(
                    task_id,
                    DeployTaskUpdate(
                        append_metadata={
                            "summary": {
                                "completed_at": utc_now().isoformat(),
                                "result": "success",
                                "commit": summary_commit,
                                "git_commit": commit_details,
                                "actor": actor_identity,
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
                failure_metadata: Dict[str, Any] = {
                    "timestamp": utc_now().isoformat(),
                    "error": str(exc),
                }
                if isinstance(exc, CommandExecutionError):
                    failure_metadata.update(
                        {
                            "command": " ".join(exc.command),
                            "cwd": str(exc.cwd) if exc.cwd else None,
                            "returncode": exc.returncode,
                            "stdout": exc.stdout[-500:],
                            "stderr": exc.stderr[-500:],
                        }
                    )
                    if action != "rollback" and self._is_auto_recoverable_command(exc.command):
                        auto_recovery = await self._attempt_auto_rollback(branch)
                        failure_metadata["auto_recovery"] = auto_recovery
                elif action != "rollback":
                    failure_metadata["auto_recovery"] = {"status": "skipped", "reason": "non-command failure"}
                await self.repository.update_task(
                    task_id,
                    DeployTaskUpdate(
                        append_metadata={"failure_context": failure_metadata},
                    ),
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
        metadata = dict(metadata)
        metadata.setdefault("timestamp", utc_now().isoformat())
        await self.repository.update_task(
            task_id,
            DeployTaskUpdate(
                append_metadata={status.value: metadata},
            ),
        )

    async def _prime_preflight_metadata(self, task_id: str) -> Dict[str, Any]:
        (
            diff_context,
            diff_stats,
            stage_seconds,
            warnings,
            cost_estimate,
        ) = await self._prepare_preview_inputs()
        llm_preview = await self._generate_llm_preview(diff_context)
        warnings = list(dict.fromkeys(warnings))
        if not warnings:
            warnings.append("Diff scan produced no warnings; run smoke tests before cutover.")
        risk_assessment = self._build_risk_assessment(diff_stats, warnings)
        snapshot = {
            "cost_estimate": cost_estimate,
            "risk_assessment": risk_assessment,
            "llm_preview": llm_preview,
            "generated_at": utc_now().isoformat(),
        }
        await self.repository.update_task(
            task_id,
            DeployTaskUpdate(
                append_metadata={
                    "summary": {
                        "preflight": snapshot,
                    }
                }
            ),
        )
        return snapshot

    async def _run_clone_stage(
        self,
        branch: str,
        *,
        target_commit: Optional[str] = None,
        force_push: bool = False,
    ) -> Dict[str, Any]:
        steps: list[Dict[str, Any]] = []

        commands: list[tuple[list[str], str]] = [
            (["git", "fetch", "origin"], "Fetch latest refs from origin"),
        ]

        if target_commit:
            commands.append(
                (
                    ["git", "checkout", "-B", branch, target_commit],
                    "Checkout deploy branch aligned with target commit",
                )
            )
            commands.append(
                (
                    ["git", "reset", "--hard", target_commit],
                    "Hard reset working tree to target commit",
                )
            )
        else:
            commands.append(
                (
                    ["git", "checkout", "-B", branch, f"origin/{branch}"],
                    "Checkout deploy branch aligned with origin",
                )
            )
            commands.append(
                (
                    ["git", "reset", "--hard", f"origin/{branch}"],
                    "Hard reset working tree to origin/branch",
                )
            )

        commands.append(
            (["git", "clean", "-fdx"], "Remove untracked files (full replace)")
        )

        for cmd, description in commands:
            steps.append(
                await self._run_command(
                    cmd,
                    cwd=self.chatbot_repo_path,
                    description=description,
                )
            )

        if force_push and target_commit and not self.dry_run:
            steps.append(
                await self._run_command(
                    ["git", "push", "origin", f"+{target_commit}:{branch}"],
                    cwd=self.chatbot_repo_path,
                    description="Force push branch to target commit",
                )
            )
        elif force_push and target_commit and self.dry_run:
            steps.append(
                {
                    "description": "Force push branch to target commit",
                    "command": f"git push origin +{target_commit}:{branch}",
                    "cwd": str(self.chatbot_repo_path),
                    "dry_run": True,
                }
            )

        return {
            "branch": branch,
            "target_commit": target_commit,
            "force_push": force_push,
            "dry_run": self.dry_run,
            "steps": steps,
        }

    async def _run_build_stage(self) -> Dict[str, Any]:
        steps: list[Dict[str, Any]] = []

        if self.frontend_install_command:
            steps.append(
                await self._run_command(
                    self.frontend_install_command,
                    cwd=self.frontend_project_path,
                    description="Install frontend dependencies",
                )
            )

        steps.append(
            await self._run_command(
                self.frontend_build_command or ["npm", "run", "build"],
                cwd=self.frontend_project_path,
                description="Build frontend application",
            )
        )

        if self.frontend_export_command:
            steps.append(
                await self._run_command(
                    self.frontend_export_command,
                    cwd=self.frontend_project_path,
                    description="Export static frontend assets",
                )
            )

        return {
            "project_path": str(self.frontend_project_path),
            "output_path": str(self.frontend_build_output_path)
            if self.frontend_build_output_path
            else None,
            "dry_run": self.dry_run,
            "steps": steps,
        }

    async def _run_cutover_stage(self) -> Dict[str, Any]:
        if self.frontend_build_output_path is None:
            return {
                "skipped": True,
                "reason": "No build output directory configured; assuming dev server mode.",
                "dry_run": self.dry_run,
            }

        build_dir = self.frontend_build_output_path
        current_target = self._resolve_live_target()
        next_target = self._select_next_target(current_target)
        metadata: Dict[str, Any] = {
            "source": str(self._normalize_path(build_dir)),
            "next_target": str(self._normalize_path(next_target)),
            "previous_target": str(self._normalize_path(current_target)) if current_target else None,
            "live_symlink": str(self._normalize_path(self.nginx_live_symlink)),
            "dry_run": self.dry_run,
        }
        if self.dry_run:
            return metadata

        if not build_dir.exists():
            raise RuntimeError(f"build directory missing: {build_dir}")
        if not build_dir.is_dir():
            raise RuntimeError(f"build output is not a directory: {build_dir}")

        next_target.parent.mkdir(parents=True, exist_ok=True)
        if next_target.exists():
            shutil.rmtree(next_target)
        shutil.copytree(build_dir, next_target)

        if self.nginx_live_symlink.exists() or self.nginx_live_symlink.is_symlink():
            self.nginx_live_symlink.unlink()
        self.nginx_live_symlink.symlink_to(next_target, target_is_directory=True)

        metadata["copied"] = True
        metadata["switched"] = True
        return metadata

    async def _run_observability_stage(self) -> Dict[str, Any]:
        # Placeholder for future Lighthouse or monitoring integrations.
        return {
            "message": "Observability checks are not implemented yet.",
            "dry_run": self.dry_run,
        }

    async def describe_blue_green_state(self) -> Dict[str, Any]:
        active_target = self._resolve_live_target()
        active_slot = self._slot_from_path(active_target)

        if self.dev_server_mode:
            next_cutover_target = "dev-server"
            standby_slot: Optional[str] = None
        else:
            next_target = self._select_next_target(active_target)
            next_cutover_target = self._slot_from_path(next_target)
            standby_slot = (
                "blue"
                if active_slot == "green"
                else "green"
                if active_slot == "blue"
                else (next_cutover_target if next_cutover_target in {"green", "blue"} else None)
            )

        last_cutover_at = await self._resolve_last_cutover_timestamp()

        return {
            "active_slot": active_slot,
            "standby_slot": standby_slot,
            "last_cutover_at": last_cutover_at,
            "next_cutover_target": next_cutover_target,
        }

    @staticmethod
    def _normalize_path(path: Path) -> Path:
        return path.resolve(strict=False)

    def _resolve_live_target(self) -> Optional[Path]:
        symlink = self.nginx_live_symlink
        if not symlink.exists() and not symlink.is_symlink():
            return None
        if symlink.is_symlink():
            target = Path(os.readlink(symlink))
            if not target.is_absolute():
                target = (symlink.parent / target)
            else:
                target = target
            return self._normalize_path(target)
        return self._normalize_path(symlink)

    def _select_next_target(self, current_target: Optional[Path]) -> Path:
        if current_target is None:
            return self.nginx_green_path

        current_norm = self._normalize_path(current_target)
        green_norm = self._normalize_path(self.nginx_green_path)
        blue_norm = self._normalize_path(self.nginx_blue_path)

        if current_norm == green_norm:
            return self.nginx_blue_path
        if current_norm == blue_norm:
            return self.nginx_green_path

        # Unknown target; default to cycling back to green.
        return self.nginx_green_path

    def _slot_from_path(self, target: Optional[Path]) -> str:
        if target is None:
            return "unknown"
        normalized = self._normalize_path(target)
        if normalized == self._normalize_path(self.nginx_green_path):
            return "green"
        if normalized == self._normalize_path(self.nginx_blue_path):
            return "blue"
        return "unknown"

    async def _resolve_last_cutover_timestamp(self) -> Optional[str]:
        try:
            successes = await self.repository.get_recent_successes(
                branch=self.default_branch,
                limit=1,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Failed to read recent successes for blue/green state: %s", exc)
            return None

        if not successes:
            return None

        latest = successes[0]
        metadata = latest.metadata or {}
        cutover_meta = metadata.get(DeployStatus.RUNNING_CUTOVER.value, {})
        if isinstance(cutover_meta, dict):
            timestamp = cutover_meta.get("timestamp")
            if timestamp:
                return timestamp

        summary = metadata.get("summary")
        if isinstance(summary, dict):
            return summary.get("completed_at")
        return None

    async def _get_current_commit(self) -> str:
        result = await self._run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=self.chatbot_repo_path,
            description="Resolve current commit SHA",
        )
        if self.dry_run:
            return "dry-run"
        stdout = result.get("stdout", "").strip()
        if not stdout:
            raise RuntimeError("Unable to resolve current commit SHA")
        return stdout

    async def _get_commit_details(self) -> Dict[str, Any]:
        if self.dry_run:
            actor = self._resolve_actor_identity()
            return {
                "sha": "dry-run",
                "author": actor,
                "authored_at": utc_now().isoformat(),
            }
        result = await self._run_command(
            ["git", "log", "-1", "--pretty=format:%H%x1f%an%x1f%ae%x1f%ad"],
            cwd=self.chatbot_repo_path,
            description="Describe latest commit metadata",
        )
        stdout = result.get("stdout", "").strip()
        sha, author_name, author_email, authored_at = (stdout.split("\x1f") + ["", "", "", ""])[:4]
        payload: Dict[str, Any] = {
            "sha": sha or None,
            "author": {
                "name": author_name or None,
                "email": author_email or None,
            },
            "authored_at": authored_at or None,
        }
        return payload

    async def _resolve_preview_context(self) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "ready": False,
            "reason": None,
            "base_commit": None,
            "head_commit": None,
            "diff_output": "",
            "diff_stats": {},
            "diff_source": "working_tree",
            "compare_metadata": None,
        }

        try:
            successes = await self.repository.get_recent_successes(
                branch=self.default_branch,
                limit=1,
            )
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.exception("Failed to read recent successes: %s", exc)
            context["reason"] = f"Unable to read deploy history: {exc}"
            return context

        base_commit: Optional[str] = None
        if successes:
            summary = successes[0].metadata.get("summary")
            if isinstance(summary, dict):
                base_commit = summary.get("commit")

        if not self._looks_like_commit(base_commit):
            context["reason"] = "No previous successful deployment to diff against."
            context["base_commit"] = base_commit
            return context

        context["base_commit"] = base_commit

        head_commit = await self._get_current_commit()
        context["head_commit"] = head_commit
        if not self._looks_like_commit(head_commit):
            context["reason"] = "Current HEAD is not a valid commit."
            return context
        if head_commit == base_commit:
            context["reason"] = "Working tree matches last successful deployment."
            return context

        diff_source = "working_tree"
        compare_metadata: Optional[Dict[str, Any]] = None
        diff_output: str
        diff_stats: Dict[str, Any]

        compare_result = await self._fetch_compare_diff(base_commit, head_commit)
        if compare_result:
            diff_source = "github_compare"
            diff_output = compare_result.get("diff_output", "")
            diff_stats = compare_result.get("diff_stats", {})
            compare_metadata = compare_result.get("compare_metadata")
        else:
            diff_output, diff_stats = await self._collect_diff_details(base_commit)

        context.update(
            {
                "ready": True,
                "diff_output": diff_output,
                "diff_stats": diff_stats,
                "diff_source": diff_source,
                "compare_metadata": compare_metadata,
            }
        )
        return context

    async def _collect_diff_details(self, base_commit: str) -> tuple[str, Dict[str, Any]]:
        diff_result = await self._run_command(
            ["git", "diff", "--name-status", f"{base_commit}..HEAD"],
            cwd=self.chatbot_repo_path,
            description="Collect diff summary for preview",
        )
        diff_output = diff_result.get("stdout", "").strip()
        diff_stats = self._summarize_diff(diff_output)
        return diff_output, diff_stats

    def _should_use_github_compare(self) -> bool:
        return self.preview_use_github_compare and bool(self.github_compare_repo)

    def _github_compare_cache_key(self, base_commit: str, head_ref: str) -> str:
        return f"{self.github_compare_repo}:{base_commit}:{head_ref}"

    async def _fetch_compare_diff(
        self, base_commit: str, head_commit: str
    ) -> Optional[Dict[str, Any]]:
        if not self._should_use_github_compare():
            return None

        head_ref = self.github_compare_head_ref or head_commit
        cache_key = self._github_compare_cache_key(base_commit, head_ref)
        ttl = self.github_compare_cache_seconds
        now = time.time()
        if ttl > 0:
            cached = self._compare_cache.get(cache_key)
            if cached and cached[0] > now:
                return cached[1]

        try:
            payload = await asyncio.to_thread(
                self._call_github_compare_api,
                base_commit,
                head_ref,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.warning("GitHub Compare API failed, falling back to local diff: %s", exc)
            return None

        diff_output, diff_stats = self._extract_compare_diff(payload)
        result: Dict[str, Any] = {
            "diff_output": diff_output,
            "diff_stats": diff_stats,
            "compare_metadata": {
                "html_url": payload.get("html_url"),
                "permalink_url": payload.get("permalink_url"),
                "compare_url": payload.get("compare_url"),
                "ahead_by": payload.get("ahead_by"),
                "behind_by": payload.get("behind_by"),
                "total_commits": payload.get("total_commits"),
                "status": payload.get("status"),
                "base_commit": base_commit,
                "head": head_ref,
            },
        }

        if ttl > 0:
            self._compare_cache[cache_key] = (now + ttl, result)
        return result

    def _call_github_compare_api(self, base_commit: str, head_ref: str) -> Dict[str, Any]:
        if not self.github_compare_repo:
            raise RuntimeError("GitHub compare repository is not configured.")

        base = urllib_parse.quote(base_commit.strip())
        head = urllib_parse.quote(head_ref.strip())
        url = f"https://api.github.com/repos/{self.github_compare_repo}/compare/{base}...{head}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "cherry-deploy-preview",
        }
        if self.github_compare_token:
            headers["Authorization"] = f"Bearer {self.github_compare_token}"

        request = urllib_request.Request(url, headers=headers, method="GET")
        try:
            with urllib_request.urlopen(request, timeout=15) as response:
                body = response.read()
        except urllib_error.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.read().decode("utf-8", errors="ignore")
            except Exception:  # pragma: no cover - defensive
                error_body = ""
            details = error_body or exc.reason
            raise RuntimeError(f"GitHub compare HTTP {exc.code}: {details}") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"GitHub compare request failed: {exc.reason}") from exc

        try:
            return json.loads(body.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            raise RuntimeError("Failed to parse GitHub compare response") from exc

    def _extract_compare_diff(self, payload: Dict[str, Any]) -> tuple[str, Dict[str, Any]]:
        files = payload.get("files")
        lines: List[str] = []
        if isinstance(files, list):
            for entry in files:
                if not isinstance(entry, dict):
                    continue
                filename = entry.get("filename") or entry.get("previous_filename")
                if not filename:
                    continue
                status = (entry.get("status") or "modified").lower()
                status_map = {
                    "added": "A",
                    "modified": "M",
                    "changed": "M",
                    "removed": "D",
                    "deleted": "D",
                    "renamed": "R",
                }
                code = status_map.get(status, "M")
                lines.append(f"{code}\t{filename}")
        diff_output = "\n".join(lines)
        diff_stats = self._summarize_diff(diff_output)
        return diff_output, diff_stats

    @staticmethod
    def _summarize_diff(diff_output: str) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "file_count": 0,
            "added": 0,
            "modified": 0,
            "deleted": 0,
            "lockfile_changed": False,
            "config_changed": False,
            "env_changed": False,
            "test_files_changed": False,
            "sensitive_changed": False,
            "paths": [],
            "warnings": [],
        }

        if not diff_output:
            stats["risk_level"] = "low"
            return stats

        warnings: List[str] = []
        for raw_line in diff_output.splitlines():
            parts = raw_line.split("\t", 1)
            if len(parts) != 2:
                continue
            status_code, path = parts
            stats["file_count"] += 1
            stats["paths"].append(path)
            code = status_code.strip().upper() or "M"
            if code.startswith("A"):
                stats["added"] += 1
            elif code.startswith("D"):
                stats["deleted"] += 1
            else:
                stats["modified"] += 1

            lowered = path.lower()
            if any(token in lowered for token in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}):
                stats["lockfile_changed"] = True
            if lowered.endswith(".env") or "secrets" in lowered:
                stats["env_changed"] = True
            if any(lowered.endswith(ext) for ext in {".yml", ".yaml", ".json"}) and (
                "infra" in lowered or "deploy" in lowered or "config" in lowered
            ):
                stats["config_changed"] = True
            if any(keyword in lowered for keyword in {"secret", "cert", ".pem", ".key", ".crt"}):
                stats["sensitive_changed"] = True
            if any(part in lowered for part in {"tests/", "/test/", ".spec", ".test"}):
                stats["test_files_changed"] = True

        if stats["lockfile_changed"]:
            warnings.append("Detected lockfile changes; npm install may take longer.")
        if stats["env_changed"]:
            warnings.append("Environment-related file modified; verify secrets.")
        if stats["config_changed"]:
            warnings.append("Configuration files updated; double-check blue/green sync.")
        if stats["sensitive_changed"]:
            warnings.append("Sensitive configuration detected in diff; rotate credentials if needed.")
        if stats["test_files_changed"]:
            warnings.append("Test files updated; ensure the relevant suites have been executed.")
        if stats["file_count"] >= 20:
            warnings.append("Large diff detected; smoke-test both frontend and API.")

        if stats["file_count"] < 5 and not stats["env_changed"] and not stats["config_changed"]:
            risk = "low"
        elif stats["file_count"] < 15 and not stats["env_changed"]:
            risk = "medium"
        else:
            risk = "high"

        stats["risk_level"] = risk
        stats["warnings"] = warnings
        return stats

    async def get_preview(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """Return a preview payload with risk/cost notes for the deploy command."""
        command_plan = [
            "git fetch origin",
            f"git checkout -B {self.default_branch} origin/{self.default_branch}",
            f"git reset --hard origin/{self.default_branch}",
            "git clean -fdx",
        ]

        if self.frontend_install_command:
            command_plan.append(" ".join(self.frontend_install_command))

        build_cmd = self.frontend_build_command or ["npm", "run", "build"]
        command_plan.append(" ".join(build_cmd))

        if self.frontend_export_command:
            command_plan.append(" ".join(self.frontend_export_command))

        if self.frontend_build_output_path:
            command_plan.append("sync static assets to nginx green path")
        else:
            command_plan.append("no static cutover (dev-server mode)")

        (
            diff_context,
            diff_stats,
            stage_seconds,
            warnings,
            cost_estimate,
        ) = await self._prepare_preview_inputs()
        timeline_preview = self._build_estimated_timeline(stage_seconds)

        llm_preview = await self._generate_llm_preview(diff_context)

        task_context: Optional[Dict[str, Any]] = None
        if task_id:
            task = await self.repository.get_task(task_id)
            if not task:
                raise RuntimeError(f"deploy task not found: {task_id}")
            stage_snapshots = self._extract_stage_snapshots(task.metadata)
            timeline_preview = self._build_timeline_from_stage_data(stage_seconds, stage_snapshots)
            task_context = self._assemble_task_context(task)
            if task.metadata.get("failure_context"):
                warnings.append("Task has failure_context metadata attached.")
            if task.error_log:
                warnings.append("Task produced an error_log entry.")

        warnings = list(dict.fromkeys(warnings))
        if not warnings:
            warnings.append("Diff scan produced no warnings; run smoke tests before cutover.")
        risk_assessment = self._build_risk_assessment(diff_stats, warnings)
        blue_green_plan = await self.describe_blue_green_state()

        return {
            "current_branch": self.default_branch,
            "target_repo": str(self.chatbot_repo_path),
            "frontend_project_path": str(self.frontend_project_path),
            "frontend_output_path": str(self.frontend_build_output_path)
            if self.frontend_build_output_path
            else None,
            "commands": command_plan,
            "risk_assessment": risk_assessment,
            "cost_estimate": cost_estimate,
            "llm_preview": llm_preview,
            "timeline_preview": timeline_preview,
            "warnings": warnings,
            "task_context": task_context,
            "blue_green_plan": blue_green_plan,
            "diff_source": diff_context.get("diff_source", "working_tree"),
            "diff_stats": diff_stats,
            "compare_metadata": diff_context.get("compare_metadata"),
        }

    async def estimate_runtime_minutes(self) -> int:
        diff_context = await self._resolve_preview_context()
        diff_stats = diff_context.get("diff_stats", {})
        stage_seconds = self._estimate_stage_seconds(diff_stats)
        cost_estimate = self._estimate_cost_summary(stage_seconds, diff_stats)
        return int(cost_estimate.get("runtime_minutes", 8))

    async def list_recent_tasks(self, limit: int = 5) -> list[Dict[str, Any]]:
        tasks = await self.repository.get_recent_tasks(limit=limit)
        summaries: list[Dict[str, Any]] = []
        for task in tasks:
            summaries.append(self._assemble_task_context(task))
        return summaries

    async def get_task_logs(self, task_id: str) -> Dict[str, Any]:
        task = await self.repository.get_task(task_id)
        if not task:
            raise RuntimeError(f"deploy task not found: {task_id}")
        stage_snapshots = self._extract_stage_snapshots(task.metadata)
        return {
            "task_id": task.task_id,
            "status": task.status,
            "stages": stage_snapshots,
            "metadata": task.metadata,
            "error_log": task.error_log,
            "failure_context": task.metadata.get("failure_context"),
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
            "dry_run": self.dry_run,
        }

        if self.dry_run:
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
            raise CommandExecutionError(
                command=command,
                cwd=cwd,
                returncode=process.returncode,
                stdout=metadata["stdout"],
                stderr=metadata["stderr"],
            )

        return metadata

    def _is_auto_recoverable_command(self, command: list[str]) -> bool:
        if not command:
            return False
        first = command[0]
        if first == "npm" and len(command) >= 2 and command[1] in {"install", "ci"}:
            return True
        if first == "bash" and any("pm2 start npm" in part for part in command if isinstance(part, str)):
            return True
        if first == "pm2" and len(command) > 1 and command[1] == "start":
            return True
        return False

    async def _attempt_auto_rollback(self, branch: str) -> Dict[str, Any]:
        logger.warning("Attempting automatic rollback for branch=%s", branch)
        try:
            task, target_commit, current_commit, branch_value = await self.prepare_rollback(branch)
        except Exception as exc:  # pylint: disable=broad-except
            logger.error("Auto rollback skipped (prepare failed): %s", exc)
            return {
                "status": "skipped",
                "reason": str(exc),
            }

        try:
            await self.perform_rollback(task.task_id, branch_value, target_commit, current_commit)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Auto rollback execution failed task=%s error=%s", task.task_id, exc)
            return {
                "status": "failed",
                "rollback_task_id": task.task_id,
                "error": str(exc),
            }

        logger.info(
            "Auto rollback succeeded task=%s rolled_back_to=%s", task.task_id, target_commit
        )
        return {
            "status": "completed",
            "rollback_task_id": task.task_id,
            "rolled_back_to": target_commit,
        }

    async def _generate_llm_preview(self, diff_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        def _fallback(message: str) -> Dict[str, Any]:
            return {
                "summary": message,
                "highlights": [],
                "risks": [],
            }

        if not self.settings.gemini_api_key:
            return _fallback("Gemini API key not configured.")

        context = diff_context or await self._resolve_preview_context()
        base_commit = context.get("base_commit")
        head_commit = context.get("head_commit")
        diff_output = context.get("diff_output", "")

        if not context.get("ready"):
            reason = context.get("reason", "Diff context unavailable.")
            return _fallback(reason)

        if len(diff_output) > self.settings.preview_diff_max_chars:
            diff_output = diff_output[: self.settings.preview_diff_max_chars] + "\n… (truncated)"

        prompt = textwrap.dedent(
            f"""
            You are an expert release engineer. Summarize the upcoming deployment changes for a teammate.

            Branch: {self.default_branch}
            Base commit (last successful deploy): {base_commit}
            Target commit (current HEAD): {head_commit}

            Git diff (name-status):
            {diff_output or '(no file changes listed)'}

            Respond ONLY with compact JSON that matches:
            {{
              "summary": "<one-sentence overview>",
              "highlights": ["<key change>", "<another highlight>"],
              "risks": ["<risk or validation reminder>"]
            }}
            Limit highlights and risks to at most three short entries each.
            """
        ).strip()

        try:
            summary_text = await asyncio.to_thread(self._call_gemini, prompt)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Gemini preview generation failed: %s", exc)
            return _fallback(f"Failed to generate preview: {exc}")

        structured = self._coerce_llm_preview(summary_text)
        if not structured["summary"]:
            structured["summary"] = (
                f"Planned updates between {base_commit or 'previous'} and {head_commit or 'current'}."
            )
        return structured

    def _call_gemini(self, prompt: str) -> str:
        genai.configure(api_key=self.settings.gemini_api_key)
        model = genai.GenerativeModel(self.settings.preview_llm_model)
        response = model.generate_content(prompt)
        if hasattr(response, "text") and response.text:
            return response.text
        if getattr(response, "candidates", None):
            parts: list[str] = []
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []):
                    text = getattr(part, "text", None)
                    if text:
                        parts.append(text)
            if parts:
                return "\n".join(parts)
        return "LLM did not return any content."

    def _coerce_llm_preview(self, raw_text: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "summary": "",
            "highlights": [],
            "risks": [],
        }
        if not raw_text:
            payload["summary"] = "LLM did not return any content."
            return payload

        candidate = raw_text.strip()
        fence_match = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL | re.IGNORECASE)
        if fence_match:
            candidate = fence_match.group(1).strip()

        parsed: Optional[Dict[str, Any]] = None
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            pass

        if isinstance(parsed, dict):
            summary = str(parsed.get("summary") or "").strip()
            highlights = [
                str(item).strip()
                for item in parsed.get("highlights", [])
                if isinstance(item, (str, int, float)) and str(item).strip()
            ]
            risks = [
                str(item).strip()
                for item in parsed.get("risks", [])
                if isinstance(item, (str, int, float)) and str(item).strip()
            ]
            payload["summary"] = summary
            payload["highlights"] = highlights[:3]
            payload["risks"] = risks[:3]
            return payload

        lines = [line.strip() for line in candidate.splitlines() if line.strip()]
        summary_line = lines[0] if lines else "LLM preview unavailable."
        highlight_lines: List[str] = []
        risk_lines: List[str] = []
        for line in lines[1:]:
            normalized = line.lstrip("-•* ").strip()
            if not normalized:
                continue
            if "risk" in normalized.lower():
                risk_lines.append(normalized)
            else:
                highlight_lines.append(normalized)

        payload["summary"] = summary_line
        payload["highlights"] = highlight_lines[:3]
        payload["risks"] = risk_lines[:3]
        return payload

    def _to_display_time(self, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(self.display_timezone)

    def as_display_time(self, value: Optional[datetime]) -> Optional[datetime]:
        return self._to_display_time(value)

    def _resolve_actor_identity(self) -> Dict[str, Optional[str]]:
        env_name = (
            os.getenv("DEPLOY_ACTOR")
            or os.getenv("DEPLOY_REQUESTER")
            or os.getenv("GITHUB_ACTOR")
            or os.getenv("USER")
            or ""
        ).strip()
        try:
            system_name = getpass.getuser()
        except Exception:  # pragma: no cover - defensive
            system_name = ""
        name = env_name or system_name or "cherry-operator"
        email = (
            os.getenv("DEPLOY_ACTOR_EMAIL")
            or os.getenv("DEPLOY_REQUESTER_EMAIL")
            or os.getenv("GITHUB_ACTOR_EMAIL")
            or os.getenv("EMAIL")
            or ""
        ).strip() or None
        return {"name": name, "email": email}

    def _attach_actor_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(metadata)
        actor = self._resolve_actor_identity()
        if actor.get("name"):
            enriched.setdefault("actor", actor["name"])
            enriched.setdefault("requested_by", actor["name"])
        if actor.get("email"):
            enriched.setdefault("requested_by_email", actor["email"])
        enriched.setdefault("trigger", enriched.get("trigger") or "api")
        return enriched
