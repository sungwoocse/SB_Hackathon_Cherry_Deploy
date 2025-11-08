from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple

import jwt
from fastapi import Cookie, HTTPException, Response, status

from settings import Settings


class AuthService:
    """Handles credential verification, JWT issuance, and cookie helpers."""

    algorithm = "HS256"

    def __init__(self, settings: Settings):
        self.login_user = settings.login_user
        self.login_password = settings.login_password
        self.jwt_secret_key = settings.jwt_secret_key
        self.jwt_expire_minutes = int(settings.jwt_expire_minutes or 60)
        self.cookie_name = settings.auth_cookie_name
        self.cookie_secure = bool(settings.auth_cookie_secure)
        self.cookie_domain = (settings.auth_cookie_domain or "").strip() or None

        if not self.jwt_secret_key or self.jwt_secret_key == "change-me":
            raise RuntimeError("JWT_SECRET_KEY must be configured with a non-default value.")

    def verify_credentials(self, username: str, password: str) -> bool:
        return username == self.login_user and password == self.login_password

    def create_access_token(self, subject: str) -> Tuple[str, datetime]:
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(minutes=self.jwt_expire_minutes)
        payload = {
            "sub": subject,
            "iat": int(issued_at.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        token = jwt.encode(payload, self.jwt_secret_key, algorithm=self.algorithm)
        return token, expires_at

    def set_auth_cookie(self, response: Response, token: str, expires_at: Optional[datetime] = None) -> None:
        max_age = self.jwt_expire_minutes * 60
        response.set_cookie(
            key=self.cookie_name,
            value=token,
            httponly=True,
            secure=self.cookie_secure,
            samesite="lax",
            max_age=max_age,
            expires=int(expires_at.timestamp()) if expires_at else max_age,
            domain=self.cookie_domain,
            path="/",
        )

    def clear_auth_cookie(self, response: Response) -> None:
        response.delete_cookie(
            key=self.cookie_name,
            domain=self.cookie_domain,
            path="/",
        )

    def require_user(self, token: Optional[str]) -> Dict[str, str]:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication cookie missing.",
            )
        try:
            payload = jwt.decode(token, self.jwt_secret_key, algorithms=[self.algorithm])
        except jwt.ExpiredSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication token expired.",
            ) from exc
        except jwt.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication token.",
            ) from exc

        subject = payload.get("sub")
        if subject != self.login_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unknown authentication subject.",
            )
        return {"username": subject}

    def build_auth_dependency(self):
        async def dependency(
            auth_token: Optional[str] = Cookie(default=None, alias=self.cookie_name)
        ) -> Dict[str, str]:
            return self.require_user(auth_token)

        return dependency
