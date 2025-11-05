from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from domain import DeployStatus
from schemas import DeployPreviewResponse, DeployRequest, DeployResponse, DeployStatusResponse
from services import DeployService


def build_deploy_router(deploy_service: DeployService) -> APIRouter:
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

        return DeployResponse(task_id=task.task_id, status=task.status)

    @router.get(
        "/status/{task_id}",
        response_model=DeployStatusResponse,
        summary="Get current deployment state",
    )
    async def get_status(task_id: str) -> DeployStatusResponse:
        try:
            task = await deploy_service.get_task(task_id)
        except RuntimeError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        return DeployStatusResponse(
            task_id=task.task_id,
            status=task.status,
            metadata=task.metadata,
            started_at=task.started_at,
            completed_at=task.completed_at,
            error_log=task.error_log,
        )

    @router.get(
        "/preview",
        response_model=DeployPreviewResponse,
        summary="Show expected actions, risk, and cost for the next deploy run",
    )
    async def preview() -> DeployPreviewResponse:
        payload = await deploy_service.get_preview()
        return DeployPreviewResponse.model_validate(payload)

    return router
