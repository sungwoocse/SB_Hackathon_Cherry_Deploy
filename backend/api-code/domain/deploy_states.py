from __future__ import annotations

from enum import Enum


class DeployStatus(str, Enum):
    PENDING = "pending"
    RUNNING_CLONE = "running_clone"
    RUNNING_BUILD = "running_build"
    RUNNING_CUTOVER = "running_cutover"
    RUNNING_OBSERVABILITY = "running_observability"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        return self in {DeployStatus.COMPLETED, DeployStatus.FAILED}


DEFAULT_STATUS_SEQUENCE: tuple[DeployStatus, ...] = (
    DeployStatus.PENDING,
    DeployStatus.RUNNING_CLONE,
    DeployStatus.RUNNING_BUILD,
    DeployStatus.RUNNING_CUTOVER,
    DeployStatus.RUNNING_OBSERVABILITY,
    DeployStatus.COMPLETED,
)


def is_valid_transition(current: DeployStatus, new: DeployStatus) -> bool:
    if current == new:
        return True
    sequence = list(DEFAULT_STATUS_SEQUENCE)
    try:
        current_index = sequence.index(current)
    except ValueError:
        return False
    if new == DeployStatus.FAILED:
        return True
    try:
        new_index = sequence.index(new)
    except ValueError:
        return False
    return new_index >= current_index
