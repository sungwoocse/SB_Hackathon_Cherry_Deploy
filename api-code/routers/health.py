from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from typing import Any, Dict, Tuple

from fastapi import APIRouter

from services import DeployService


PM2_TARGETS: Tuple[str, ...] = ("main-api", "frontend-dev")


def build_health_router(deploy_service: DeployService) -> APIRouter:
    router = APIRouter()

    @router.get("/healthz")
    async def healthcheck() -> Dict[str, Any]:
        pm2_task = asyncio.create_task(_collect_pm2_states(PM2_TARGETS))

        mongo_ok = await deploy_service.repository.ping()
        latest_task = await deploy_service.repository.get_latest_task()

        pm2_states = await pm2_task
        issues = []
        if not mongo_ok:
            issues.append("MongoDB ping failed.")
        for name, status in pm2_states.items():
            if status not in {"online", "launching"}:
                issues.append(f"pm2:{name} is {status}.")

        overall_status = "healthy" if not issues else "degraded"

        response: Dict[str, Any] = {
            "status": overall_status,
            "pm2_processes": pm2_states,
            "mongo": "ok" if mongo_ok else "unreachable",
            "last_task_id": latest_task.task_id if latest_task else None,
            "last_task_status": latest_task.status if latest_task else None,
            "issues": issues,
        }
        return response

    return router


async def _collect_pm2_states(targets: Tuple[str, ...]) -> Dict[str, str]:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _read_pm2_states, targets)


def _read_pm2_states(targets: Tuple[str, ...]) -> Dict[str, str]:
    pm2_path = shutil.which("pm2")
    if not pm2_path:
        return {name: "unavailable" for name in targets}

    try:
        completed = subprocess.run(  # noqa: S603
            [pm2_path, "jlist"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
    except Exception:  # pragma: no cover - fallback path
        return {name: "unknown" for name in targets}

    if completed.returncode != 0:
        return {name: "unknown" for name in targets}

    try:
        process_list = json.loads(completed.stdout or "[]")
    except json.JSONDecodeError:
        process_list = []

    mapping: Dict[str, str] = {}
    for name in targets:
        status = "missing"
        for proc in process_list:
            if proc.get("name") == name:
                status = proc.get("pm2_env", {}).get("status", "unknown")
                break
        mapping[name] = status
    return mapping
