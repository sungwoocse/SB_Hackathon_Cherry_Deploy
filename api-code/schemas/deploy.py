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
    branch: str = Field(..., description="Branch slated for this operation.")
    action: str = Field(..., description="deploy or rollback.")
    queued_at: datetime = Field(..., description="Timestamp when the task was enqueued.")
    estimated_duration_minutes: int = Field(
        ..., description="Rough ETA based on historical stage durations."
    )
    context: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional contextual information (e.g., rollback from/to commits).",
    )
    dev_server_restart_planned: bool = Field(
        default=False,
        description="True when the pipeline restarts the dev server instead of serving static assets.",
    )


class DeployStatusResponse(BaseModel):
    task_id: str = Field(..., description="Deployment task identifier.")
    status: DeployStatus = Field(..., description="Current task status.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Per-stage metadata.")
    stages: Dict[str, Any] = Field(
        default_factory=dict,
        description="Convenience snapshot of running_* stages with stdout/stderr information.",
    )
    started_at: datetime = Field(..., description="UTC timestamp when task was created.")
    completed_at: Optional[datetime] = Field(
        default=None, description="UTC timestamp when task reached a terminal state."
    )
    error_log: Optional[str] = Field(
        default=None, description="Failure details if the task status is failed."
    )
    failure_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Auto-recovery metadata captured when failures occur."
    )


class DeployPreviewResponse(BaseModel):
    current_branch: str = Field(..., description="Default branch targeted for deploy operations.")
    target_repo: str = Field(..., description="Filesystem path of the frontend repository.")
    frontend_project_path: Optional[str] = Field(
        default=None, description="Absolute path to the frontend project used for builds."
    )
    frontend_output_path: Optional[str] = Field(
        default=None,
        description="Absolute path of the generated artifacts (if any). Absent in dev-server mode.",
    )
    commands: list[str] = Field(..., description="Ordered commands executed during deploy.")
    risk_assessment: Dict[str, Any] = Field(..., description="Plain-language risk summary.")
    cost_estimate: Dict[str, Any] = Field(..., description="Rough execution cost/time details.")
    llm_preview: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Gemini-generated summary of the upcoming deploy diff. Contains status, diff snippet, and response text when available.",
    )
    timeline_preview: list[Dict[str, Any]] = Field(
        ..., description="Ordered timeline with expected seconds per stage."
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Human-readable warnings derived from diff/task context.",
    )
    task_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Snapshot of a specific task when task_id is provided."
    )


class RollbackRequest(BaseModel):
    branch: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Optional branch override to roll back (defaults to deploy).",
    )


class DeployTaskSummary(BaseModel):
    task_id: str = Field(..., description="Task identifier.")
    status: DeployStatus = Field(..., description="Current or terminal status.")
    branch: str = Field(..., description="Associated branch.")
    action: str = Field(..., description="Operation type, e.g., deploy or rollback.")
    started_at: datetime = Field(..., description="UTC creation timestamp.")
    completed_at: Optional[datetime] = Field(
        default=None, description="UTC completion timestamp when finished."
    )
    summary: Optional[Dict[str, Any]] = Field(
        default=None, description="Summary info stored once the pipeline completes."
    )
    failure_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Failure metadata captured on errors."
    )


class DeployTaskLogResponse(BaseModel):
    task_id: str = Field(..., description="Task identifier.")
    status: DeployStatus = Field(..., description="Current status.")
    stages: Dict[str, Any] = Field(..., description="running_* stage metadata.")
    metadata: Dict[str, Any] = Field(..., description="Full metadata payload.")
    error_log: Optional[str] = Field(default=None, description="Task-level error log.")
    failure_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Failure context describing remediation attempts."
    )
