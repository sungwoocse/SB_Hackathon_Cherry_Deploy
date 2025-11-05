from __future__ import annotations

from fastapi import APIRouter


router = APIRouter()


@router.get("/healthz")
def healthcheck() -> dict[str, str]:
    """Basic liveness probe for PM2 / monitoring tooling."""
    return {"status": "ok"}
