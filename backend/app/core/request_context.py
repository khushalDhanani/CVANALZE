from __future__ import annotations
import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.error_handlers import error_response
from app.core.logging import logger
from app.schemas.contracts import ErrorCode

_SAFE_ID = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


class RequestContextMiddleware:
    """Attach safe request/correlation IDs and reject oversized JSON bodies early."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = _safe_identifier(headers.get("x-request-id")) or uuid.uuid4().hex
        correlation_id = _safe_identifier(headers.get("x-correlation-id")) or request_id
        state = scope.setdefault("state", {})
        state["request_id"] = request_id
        state["correlation_id"] = correlation_id
        started = time.perf_counter()

        if scope["type"] == "http" and _json_content_length(headers) > settings.MAX_JSON_REQUEST_SIZE_BYTES:
            logger.warning(f"[REQUEST] request_id={request_id} correlation_id={correlation_id} method={scope.get('method')} path={scope.get('path')} status=413")
            response = error_response(
                scope,
                status_code=413,
                code=ErrorCode.PAYLOAD_TOO_LARGE,
                message="JSON request body exceeds the configured size limit.",
                headers=_response_headers(headers, request_id, correlation_id),
            )
            await response(scope, receive, send)
            return

        status_code = 0
        response_started = False

        async def send_with_context(message: Message) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = int(message["status"])
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = request_id
                response_headers["X-Correlation-ID"] = correlation_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_context)
        except Exception as exc:
            if scope["type"] != "http" or response_started:
                raise
            logger.exception(f"[REQUEST_ERROR] request_id={request_id} correlation_id={correlation_id} method={scope.get('method')} path={scope.get('path')} error={type(exc).__name__}")
            response = error_response(
                scope,
                status_code=500,
                code=ErrorCode.INTERNAL_ERROR,
                message="An internal error occurred.",
                headers=_response_headers(headers, request_id, correlation_id),
            )
            await response(scope, receive, send_with_context)
        finally:
            if scope["type"] == "http":
                duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
                logger.info(
                    f"[REQUEST] request_id={request_id} correlation_id={correlation_id} method={scope.get('method')} path={scope.get('path')} status={status_code or 500} duration_ms={duration_ms}"
                )


def _safe_identifier(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized if _SAFE_ID.fullmatch(normalized) else None


def _json_content_length(headers: Headers) -> int:
    if not headers.get("content-type", "").lower().startswith("application/json"):
        return 0
    try:
        return max(0, int(headers.get("content-length", "0")))
    except ValueError:
        return 0


def _response_headers(headers: Headers, request_id: str, correlation_id: str) -> dict[str, str]:
    response_headers = {"X-Request-ID": request_id, "X-Correlation-ID": correlation_id}
    origin = headers.get("origin", "").rstrip("/")
    if origin and origin in settings.TRUSTED_ORIGINS:
        response_headers.update({"Access-Control-Allow-Origin": origin, "Vary": "Origin"})
    return response_headers
