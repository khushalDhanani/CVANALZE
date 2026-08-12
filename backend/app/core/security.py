from __future__ import annotations
import base64
import binascii
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from http.cookies import CookieError, SimpleCookie

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


SESSION_COOKIE_NAME = "cv_analyzer_session"


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

        headers = Headers(scope=scope)
        principal = authenticate_session_token(extract_session_token(headers))
        if principal is None:
            principal = authenticate_api_key(extract_api_key(headers))
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


def create_session_token(principal: AuthenticatedPrincipal, issued_at: int | None = None) -> str:
    signing_key = _session_signing_key()
    if not signing_key:
        raise ValueError("A session signing key of at least 32 characters is required.")
    timestamp = int(time.time()) if issued_at is None else issued_at
    payload = {
        "exp": timestamp + settings.AUTH_SESSION_TTL_SECONDS,
        "fingerprint": principal.key_fingerprint,
        "role": principal.role.value,
        "v": 1,
    }
    encoded_payload = _base64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(signing_key, encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"{encoded_payload}.{_base64url_encode(signature)}"


def authenticate_session_token(token: str | None, now: int | None = None) -> AuthenticatedPrincipal | None:
    if not token:
        return None
    signing_key = _session_signing_key()
    if not signing_key:
        return None
    encoded_payload, separator, encoded_signature = token.partition(".")
    if not separator or not encoded_payload or not encoded_signature:
        return None
    try:
        supplied_signature = _base64url_decode(encoded_signature)
        expected_signature = hmac.new(signing_key, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            return None
        payload = json.loads(_base64url_decode(encoded_payload))
        expires_at = int(payload["exp"])
        role = AccessTier(str(payload["role"]))
        fingerprint = str(payload["fingerprint"])
    except (binascii.Error, KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if payload.get("v") != 1 or expires_at <= (int(time.time()) if now is None else now):
        return None
    if role not in (AccessTier.RECRUITER, AccessTier.ADMINISTRATOR) or not fingerprint:
        return None
    return AuthenticatedPrincipal(role=role, key_fingerprint=fingerprint)


def extract_api_key(headers: Headers) -> str | None:
    authorization = headers.get("authorization", "").strip()
    scheme, separator, credentials = authorization.partition(" ")
    if separator and scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()
    header_key = headers.get("x-api-key", "").strip()
    return header_key or None


def extract_session_token(headers: Headers) -> str | None:
    raw_cookie = headers.get("cookie", "")
    if not raw_cookie:
        return None
    cookies = SimpleCookie()
    try:
        cookies.load(raw_cookie)
    except CookieError:
        return None
    morsel = cookies.get(SESSION_COOKIE_NAME)
    return morsel.value if morsel else None


def _matches_any(candidate: str, configured_keys: list[str]) -> bool:
    matched = False
    for configured in configured_keys:
        if configured:
            matched = hmac.compare_digest(candidate, configured) or matched
    return matched


def _fingerprint(api_key: str) -> str:
    salt = b"cv_analyzer_api_key_fingerprint_salt"
    return hmac.new(salt, api_key.encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def _session_signing_key() -> bytes | None:
    configured = settings.AUTH_SESSION_SIGNING_KEY.encode("utf-8")
    return configured if len(configured) >= 32 else None


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _role_allows(actual: AccessTier, required: AccessTier) -> bool:
    rank = {AccessTier.PUBLIC: 0, AccessTier.RECRUITER: 1, AccessTier.ADMINISTRATOR: 2}
    return rank[actual] >= rank[required]
