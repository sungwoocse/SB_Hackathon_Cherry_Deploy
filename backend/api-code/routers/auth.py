from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from schemas import LoginRequest, LoginResponse, LogoutResponse, MeResponse
from services import AuthService


def build_auth_router(auth_service: AuthService) -> APIRouter:
    router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

    auth_dependency = auth_service.build_auth_dependency()

    @router.post(
        "/login",
        response_model=LoginResponse,
        status_code=status.HTTP_200_OK,
        summary="Authenticate operator and issue auth cookie.",
    )
    async def login(payload: LoginRequest, response: Response) -> LoginResponse:
        if not auth_service.verify_credentials(payload.username, payload.password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")
        token, expires_at = auth_service.create_access_token(payload.username)
        auth_service.set_auth_cookie(response, token, expires_at)
        return LoginResponse(username=payload.username, expires_at=expires_at)

    @router.post(
        "/logout",
        response_model=LogoutResponse,
        summary="Clear auth cookie.",
    )
    async def logout(response: Response) -> LogoutResponse:
        auth_service.clear_auth_cookie(response)
        return LogoutResponse(success=True)

    @router.get(
        "/me",
        response_model=MeResponse,
        summary="Return current authenticated user.",
    )
    async def me(user=Depends(auth_dependency)) -> MeResponse:  # type: ignore[valid-type]
        return MeResponse(username=user["username"])

    return router
