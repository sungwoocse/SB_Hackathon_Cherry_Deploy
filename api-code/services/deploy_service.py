from __future__ import annotations

import asyncio
import logging
import os
import shlex
import shutil
import textwrap
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

import google.generativeai as genai

from domain import DeployStatus, is_valid_transition
from models import DeployTask, DeployTaskCreate, DeployTaskUpdate, utc_now
from repositories import DeployTaskRepository
from settings import Settings


logger = logging.getLogger("cherry-deploy.deploy")


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
        self._pipeline_lock = AsyncReentrantLock()

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
                metadata={
                    "branch": branch,
                    "action": "deploy",
                },
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
                metadata={
                    "branch": branch,
                    "action": "rollback",
                    "from_commit": current_commit,
                    "to_commit": target_commit,
                },
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
                await self.repository.update_task(
                    task_id,
                    DeployTaskUpdate(
                        append_metadata={
                            "summary": {
                                "completed_at": utc_now().isoformat(),
                                "result": "success",
                                "commit": summary_commit,
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
        await self.repository.update_task(
            task_id,
            DeployTaskUpdate(
                append_metadata={status.value: metadata},
            ),
        )

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

    async def get_preview(self) -> Dict[str, Any]:
        """Return a static preview payload with risk/cost notes for the deploy command."""
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

        llm_preview = await self._generate_llm_preview()

        return {
            "current_branch": self.default_branch,
            "target_repo": str(self.chatbot_repo_path),
            "frontend_project_path": str(self.frontend_project_path),
            "frontend_output_path": str(self.frontend_build_output_path)
            if self.frontend_build_output_path
            else None,
            "commands": command_plan,
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
            "llm_preview": llm_preview,
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

    async def _generate_llm_preview(self) -> Dict[str, Any]:
        if not self.settings.gemini_api_key:
            return {
                "status": "skipped",
                "reason": "Gemini API key not configured.",
            }

        try:
            successes = await self.repository.get_recent_successes(
                branch=self.default_branch,
                limit=1,
            )
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Failed to fetch recent successes for preview: %s", exc)
            return {
                "status": "skipped",
                "reason": f"Unable to read deploy history: {exc}",
            }

        base_commit: Optional[str] = None
        if successes:
            summary = successes[0].metadata.get("summary")
            if isinstance(summary, dict):
                base_commit = summary.get("commit")

        if not base_commit:
            return {
                "status": "skipped",
                "reason": "No previous successful deployment to diff against.",
            }

        head_commit_meta = await self._run_command(
            ["git", "rev-parse", "HEAD"],
            cwd=self.chatbot_repo_path,
            description="Resolve current commit SHA for preview",
        )
        head_commit = head_commit_meta["stdout"].strip()
        if head_commit == base_commit:
            return {
                "status": "skipped",
                "reason": "Working tree matches last successful deployment.",
            }

        diff_command = self.settings.preview_diff_command.format(base_commit=base_commit)
        diff_args = shlex.split(diff_command)
        diff_result = await self._run_command(
            diff_args,
            cwd=self.chatbot_repo_path,
            description="Collect diff summary for preview",
        )
        diff_output = diff_result.get("stdout", "").strip()
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

            Provide:
            1. Key functional changes inferred from filenames/paths.
            2. Potential risk areas or components to smoke-test.
            3. Any follow-up questions or clarifications to raise with the author.
            Keep it concise and readable in Markdown bullet format.
            """
        ).strip()

        llm_payload: Dict[str, Any] = {
            "status": "skipped",
            "reason": "Gemini call not attempted.",
            "model": self.settings.preview_llm_model,
            "base_commit": base_commit,
            "target_commit": head_commit,
            "diff_snippet": diff_output,
        }

        try:
            summary_text = await asyncio.to_thread(self._call_gemini, prompt)
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Gemini preview generation failed: %s", exc)
            llm_payload.update(
                {
                    "status": "failed",
                    "reason": str(exc),
                }
            )
            return llm_payload

        llm_payload.update(
            {
                "status": "completed",
                "response": summary_text.strip(),
            }
        )
        return llm_payload

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
