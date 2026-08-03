import hashlib
import hmac
from dataclasses import dataclass

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.access_policy import resolve_access_tier
from app.core.config import settings
from app.core.error_handlers import error_response
from app.schemas.contracts import AccessTier, ErrorCode


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    role: AccessTier
    key_fingerprint: str


class AccessControlMiddleware:
    """Enforce the characterized access policy with constant-time API-key matching."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        if scope["type"] == "http" and scope.get("method") == "OPTIONS":
            await self.app(scope, receive, send)
            return

        method = "WEBSOCKET" if scope["type"] == "websocket" else str(scope.get("method") or "GET")
        path = str(scope.get("path") or "")
        required = resolve_access_tier(method, path)
        if required is None and path.startswith("/api/"):
            required = AccessTier.ADMINISTRATOR
        if required in (None, AccessTier.PUBLIC) or not settings.AUTH_REQUIRED:
            await self.app(scope, receive, send)
            return

        if not settings.RECRUITER_API_KEYS and not settings.ADMINISTRATOR_API_KEYS:
            await self._reject(
                scope,
                receive,
                send,
                status_code=503,
                code=ErrorCode.DEPENDENCY_UNAVAILABLE,
                message="Authentication is not configured.",
            )
            return

        api_key = _extract_api_key(Headers(scope=scope))
        principal = authenticate_api_key(api_key)
        if principal is None:
            await self._reject(
                scope,
                receive,
                send,
                status_code=401,
                code=ErrorCode.UNAUTHORIZED,
                message="Valid API credentials are required.",
                headers={"WWW-Authenticate": "Bearer"},
            )
            return
        if not _role_allows(principal.role, required):
            await self._reject(
                scope,
                receive,
                send,
                status_code=403,
                code=ErrorCode.FORBIDDEN,
                message="The authenticated role cannot access this endpoint.",
            )
            return

        scope.setdefault("state", {})["principal"] = principal
        await self.app(scope, receive, send)

    @staticmethod
    async def _reject(
        scope: Scope,
        receive: Receive,
        send: Send,
        *,
        status_code: int,
        code: ErrorCode,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        if scope["type"] == "websocket":
            close_code = 4401 if status_code == 401 else 4403
            await send({"type": "websocket.close", "code": close_code, "reason": message})
            return
        response = error_response(
            scope,
            status_code=status_code,
            code=code,
            message=message,
            retryable=status_code == 503,
            headers=headers,
        )
        await response(scope, receive, send)


def authenticate_api_key(api_key: str | None) -> AuthenticatedPrincipal | None:
    if not api_key:
        return None
    if _matches_any(api_key, settings.ADMINISTRATOR_API_KEYS):
        return AuthenticatedPrincipal(AccessTier.ADMINISTRATOR, _fingerprint(api_key))
    if _matches_any(api_key, settings.RECRUITER_API_KEYS):
        return AuthenticatedPrincipal(AccessTier.RECRUITER, _fingerprint(api_key))
    return None


def _extract_api_key(headers: Headers) -> str | None:
    authorization = headers.get("authorization", "").strip()
    scheme, separator, credentials = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    header_key = headers.get("x-api-key", "").strip()
    return header_key or None


def _matches_any(candidate: str, configured_keys: list[str]) -> bool:
    matched = False
    for configured in configured_keys:
        if configured:
            matched = hmac.compare_digest(candidate, configured) or matched
    return matched


def _fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]


def _role_allows(actual: AccessTier, required: AccessTier) -> bool:
    rank = {AccessTier.PUBLIC: 0, AccessTier.RECRUITER: 1, AccessTier.ADMINISTRATOR: 2}
    return rank[actual] >= rank[required]
