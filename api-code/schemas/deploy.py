from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from domain import DeployStatus


class DeployRequest(BaseModel):
    branch: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Optional branch override. Defaults to the server configuration (deploy).",
    )


class DeployResponse(BaseModel):
    task_id: str = Field(..., description="Identifier for tracking deployment progress.")
    status: DeployStatus = Field(..., description="Initial status of the deploy task.")


class DeployStatusResponse(BaseModel):
    task_id: str = Field(..., description="Deployment task identifier.")
    status: DeployStatus = Field(..., description="Current task status.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Per-stage metadata.")
    started_at: datetime = Field(..., description="UTC timestamp when task was created.")
    completed_at: Optional[datetime] = Field(
        default=None, description="UTC timestamp when task reached a terminal state."
    )
    error_log: Optional[str] = Field(
        default=None, description="Failure details if the task status is failed."
    )


class DeployPreviewResponse(BaseModel):
    current_branch: str = Field(..., description="Default branch targeted for deploy operations.")
    target_repo: str = Field(..., description="Filesystem path of the frontend repository.")
    commands: list[str] = Field(..., description="Ordered commands executed during deploy.")
    risk_assessment: Dict[str, Any] = Field(..., description="Plain-language risk summary.")
    cost_estimate: Dict[str, Any] = Field(..., description="Rough execution cost/time details.")
