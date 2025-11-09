from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from domain import DeployStatus
from schemas import (
    DeployPreviewResponse,
    DeployRequest,
    DeployResponse,
    DeployStatusResponse,
    DeployTaskLogResponse,
    DeployTaskSummary,
    RollbackRequest,
)
from services import DeployService


def build_deploy_router(deploy_service: DeployService, auth_dependency: Callable) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["deploy"])

    @router.post(
        "/deploy",
        response_model=DeployResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="Trigger a Blue/Green deployment for the chatbot frontend.",
    )
    async def trigger_deploy(
        payload: DeployRequest,
        background_tasks: BackgroundTasks,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> DeployResponse:
        branch_input = (payload.branch or "").strip() or None
        try:
            task = await deploy_service.create_task(branch=branch_input or "")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # pragma: no cover - defensive guard
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        branch = task.metadata.get("branch", deploy_service.default_branch)

        background_tasks.add_task(
            deploy_service.run_pipeline,
            task.task_id,
            branch,
        )

        try:
            eta_minutes = await deploy_service.estimate_runtime_minutes()
        except Exception:  # pragma: no cover - fallback if preview fails
            eta_minutes = 8

        return DeployResponse(
            task_id=task.task_id,
            status=task.status,
            branch=branch,
            action="deploy",
            queued_at=deploy_service.as_display_time(task.started_at),
            estimated_duration_minutes=eta_minutes,
            context={},
            dev_server_restart_planned=deploy_service.dev_server_mode,
        )

    @router.get(
        "/status/{task_id}",
        response_model=DeployStatusResponse,
        summary="Get current deployment state",
    )
    async def get_status(
        task_id: str,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> DeployStatusResponse:
        try:
            task = await deploy_service.get_task(task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        stages = deploy_service.build_stage_snapshot(task.metadata)
        failure_context = task.metadata.get("failure_context")
        raw_summary = task.metadata.get("summary")
        summary_meta = raw_summary if isinstance(raw_summary, dict) else {}
        raw_preflight = summary_meta.get("preflight")
        preflight_meta = raw_preflight if isinstance(raw_preflight, dict) else {}
        cost_estimate = preflight_meta.get("cost_estimate")
        risk_assessment = preflight_meta.get("risk_assessment")
        llm_preview = preflight_meta.get("llm_preview")
        blue_green_plan = await deploy_service.describe_blue_green_state()

        return DeployStatusResponse(
            task_id=task.task_id,
            status=task.status,
            metadata=task.metadata,
            stages=stages,
            started_at=deploy_service.as_display_time(task.started_at),
            completed_at=deploy_service.as_display_time(task.completed_at),
            error_log=task.error_log,
            failure_context=failure_context,
            cost_estimate=cost_estimate,
            risk_assessment=risk_assessment,
            llm_preview=llm_preview,
            blue_green_plan=blue_green_plan,
            timezone=deploy_service.display_timezone_name,
        )

    @router.get(
        "/preview",
        response_model=DeployPreviewResponse,
        summary="Show expected actions, risk, and cost for the next deploy run",
    )
    async def preview(
        task_id: Optional[str] = None,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> DeployPreviewResponse:
        try:
            payload = await deploy_service.get_preview(task_id=task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return DeployPreviewResponse.model_validate(payload)

    @router.post(
        "/rollback",
        response_model=DeployResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="Rollback to the previous successful deployment commit.",
    )
    async def rollback(
        payload: RollbackRequest,
        background_tasks: BackgroundTasks,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> DeployResponse:
        try:
            task, target_commit, current_commit, branch_value = await deploy_service.prepare_rollback(
                payload.branch
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

        background_tasks.add_task(
            deploy_service.perform_rollback,
            task.task_id,
            branch_value,
            target_commit,
            current_commit,
        )

        try:
            eta_minutes = await deploy_service.estimate_runtime_minutes()
        except Exception:
            eta_minutes = 8

        context = {"from_commit": current_commit, "to_commit": target_commit}

        return DeployResponse(
            task_id=task.task_id,
            status=task.status,
            branch=branch_value,
            action="rollback",
            queued_at=deploy_service.as_display_time(task.started_at),
            estimated_duration_minutes=eta_minutes,
            context=context,
            dev_server_restart_planned=deploy_service.dev_server_mode,
        )

    @router.get(
        "/tasks/recent",
        response_model=list[DeployTaskSummary],
        summary="List recent deploy/rollback tasks.",
    )
    async def list_recent_tasks(
        limit: int = 5,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> list[DeployTaskSummary]:
        bounded_limit = max(1, min(limit, 20))
        summaries = await deploy_service.list_recent_tasks(limit=bounded_limit)
        return [DeployTaskSummary.model_validate(summary) for summary in summaries]

    @router.get(
        "/tasks/{task_id}/logs",
        response_model=DeployTaskLogResponse,
        summary="Return stdout/stderr metadata for a specific task.",
    )
    async def task_logs(
        task_id: str,
        user=Depends(auth_dependency),  # type: ignore[valid-type]
    ) -> DeployTaskLogResponse:
        try:
            payload = await deploy_service.get_task_logs(task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        payload["stages"] = deploy_service.build_stage_snapshot(payload.get("metadata", {}))
        return DeployTaskLogResponse.model_validate(payload)

    return router
