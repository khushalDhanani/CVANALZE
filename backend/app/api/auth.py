from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import settings
from app.core.security import (
    SESSION_COOKIE_NAME,
    authenticate_api_key,
    authenticate_session_token,
    create_session_token,
    extract_api_key,
    extract_session_token,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/session")
async def get_session(request: Request) -> dict[str, bool | int | str | None]:
    if not settings.AUTH_REQUIRED:
        return _session_response(authenticated=True, role="administrator", expires_in_seconds=None)
    principal = authenticate_session_token(extract_session_token(request.headers))
    return _session_response(
        authenticated=principal is not None,
        role=principal.role.value if principal else None,
        expires_in_seconds=settings.AUTH_SESSION_TTL_SECONDS if principal else None,
    )


@router.post("/session")
async def create_session(request: Request, response: Response) -> dict[str, bool | int | str | None]:
    if len(settings.AUTH_SESSION_SIGNING_KEY.encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="Browser session authentication is not configured.")
    principal = authenticate_api_key(extract_api_key(request.headers))
    if principal is None:
        raise HTTPException(status_code=401, detail="Valid API credentials are required.", headers={"WWW-Authenticate": "Bearer"})
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=create_session_token(principal),
        max_age=settings.AUTH_SESSION_TTL_SECONDS,
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="strict",
        path="/",
    )
    return _session_response(
        authenticated=True,
        role=principal.role.value,
        expires_in_seconds=settings.AUTH_SESSION_TTL_SECONDS,
    )


@router.delete("/session")
async def delete_session(response: Response) -> dict[str, bool | int | str | None]:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="strict",
        path="/",
    )
    return _session_response(authenticated=False, role=None, expires_in_seconds=None)


def _session_response(*, authenticated: bool, role: str | None, expires_in_seconds: int | None) -> dict[str, bool | int | str | None]:
    return {
        "authenticated": authenticated,
        "auth_required": settings.AUTH_REQUIRED,
        "role": role,
        "expires_in_seconds": expires_in_seconds,
    }
