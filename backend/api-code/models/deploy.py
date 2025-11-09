from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from domain.deploy_states import DeployStatus


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MongoModel(BaseModel):
    """Base Pydantic model with sensible defaults for MongoDB documents."""

    model_config = {
        "populate_by_name": True,
        "use_enum_values": True,
        "json_encoders": {datetime: lambda dt: dt.isoformat()},
    }


class DeployTask(MongoModel):
    task_id: str = Field(..., alias="_id", description="Primary identifier (UUID).")
    status: DeployStatus = Field(..., description="Current execution state.")
    started_at: datetime = Field(
        default_factory=utc_now, description="Task creation timestamp."
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Set when task reaches a terminal state."
    )
    error_log: Optional[str] = Field(
        default=None, description="Failure log captured when status == failed."
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Arbitrary metadata per stage."
    )

    def to_mongo(self) -> dict[str, Any]:
        payload = self.model_dump(by_alias=True, exclude_none=True)
        return payload

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "DeployTask":
        if not document:
            raise ValueError("Mongo document is empty; cannot build DeployTask.")
        data = {**document}
        if "_id" in data and "task_id" not in data:
            data["task_id"] = data.pop("_id")
        return cls.model_validate(data)

    def mark_completed(self) -> "DeployTask":
        self.status = DeployStatus.COMPLETED
        self.completed_at = utc_now()
        return self

    def mark_failed(self, error_log: str) -> "DeployTask":
        self.status = DeployStatus.FAILED
        self.error_log = error_log
        self.completed_at = utc_now()
        return self


class DeployTaskCreate(BaseModel):
    task_id: str
    status: DeployStatus = Field(default=DeployStatus.PENDING)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_document(self) -> dict[str, Any]:
        return DeployTask(
            _id=self.task_id,
            status=self.status,
            metadata=self.metadata,
        ).to_mongo()


class DeployTaskUpdate(BaseModel):
    status: Optional[DeployStatus] = None
    error_log: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    append_metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key/values merged into metadata (existing keys overwritten).",
    )
    completed_at: Optional[datetime] = None

    def to_update_query(self) -> dict[str, Any]:
        update: dict[str, Any] = {}
        set_fields: dict[str, Any] = {}
        if self.status is not None:
            set_fields["status"] = self.status.value
        if self.error_log is not None:
            set_fields["error_log"] = self.error_log
        if self.completed_at is not None:
            set_fields["completed_at"] = self.completed_at
        if self.metadata:
            set_fields["metadata"] = self.metadata
        if set_fields:
            update["$set"] = set_fields
        if self.append_metadata:
            flattened = _flatten_metadata_updates(self.append_metadata)
            if flattened:
                update.setdefault("$set", {})
                update["$set"].update({f"metadata.{key}": value for key, value in flattened.items()})
        return update


def _flatten_metadata_updates(values: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    flattened: Dict[str, Any] = {}
    for key, value in values.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten_metadata_updates(value, full_key))
        else:
            flattened[full_key] = value
    return flattened


class DeployReport(MongoModel):
    report_id: str = Field(..., alias="_id")
    task_id: str = Field(..., description="Foreign key to deploy_tasks._id.")
    metrics: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    def to_mongo(self) -> dict[str, Any]:
        return self.model_dump(by_alias=True, exclude_none=True)

    @classmethod
    def from_mongo(cls, document: dict[str, Any]) -> "DeployReport":
        data = {**document}
        if "_id" in data and "report_id" not in data:
            data["report_id"] = data.pop("_id")
        return cls.model_validate(data)
