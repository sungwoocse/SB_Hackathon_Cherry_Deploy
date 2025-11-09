from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., description="Operator username.")
    password: str = Field(..., description="Operator password.")


class LoginResponse(BaseModel):
    username: str = Field(..., description="Authenticated username.")
    expires_at: datetime = Field(..., description="Expiration timestamp for the issued cookie.")


class LogoutResponse(BaseModel):
    success: bool = Field(..., description="True when the cookie is cleared.")


class MeResponse(BaseModel):
    username: str = Field(..., description="Authenticated username extracted from the cookie.")
