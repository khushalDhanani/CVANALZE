from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import logger
from app.schemas.contracts import CanonicalError, ErrorCode, ErrorResponse


_STATUS_CODES: dict[int, ErrorCode] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    413: ErrorCode.PAYLOAD_TOO_LARGE,
    415: ErrorCode.UNSUPPORTED_FILE,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    503: ErrorCode.DEPENDENCY_UNAVAILABLE,
}


def request_identifiers(scope: Mapping[str, Any]) -> tuple[str | None, str | None]:
    state = scope.get("state") or {}
    return state.get("request_id"), state.get("correlation_id")


def error_payload(
    scope: Mapping[str, Any],
    *,
    code: ErrorCode,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id, correlation_id = request_identifiers(scope)
    response = ErrorResponse(
        error=CanonicalError(
            code=code,
            message=message,
            request_id=request_id,
            correlation_id=correlation_id,
            retryable=retryable,
            details=details or {},
        ),
        detail=message,
    )
    return response.model_dump(mode="json", exclude_none=True)


def error_response(
    scope: Mapping[str, Any],
    *,
    status_code: int,
    code: ErrorCode,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(
            scope,
            code=code,
            message=message,
            retryable=retryable,
            details=details,
        ),
        headers=headers,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status_code = exc.status_code
    default_code = ErrorCode.INTERNAL_ERROR if status_code >= 500 else ErrorCode.VALIDATION_ERROR
    code = _STATUS_CODES.get(status_code, default_code)
    if status_code >= 500:
        request_id, correlation_id = request_identifiers(request.scope)
        cause = exc.__cause__ or exc
        logger.error(
            f"[HTTP_ERROR] request_id={request_id} correlation_id={correlation_id} "
            f"method={request.method} path={request.url.path} status={status_code}",
            exc_info=(type(cause), cause, cause.__traceback__),
        )
        message = (
            "A required service is temporarily unavailable."
            if status_code == 503
            else "An internal error occurred."
        )
    else:
        message = _http_exception_message(exc.detail)
    return error_response(
        request.scope,
        status_code=status_code,
        code=code,
        message=message,
        retryable=status_code in (429, 503),
        headers=exc.headers,
    )


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    details = {
        "violations": [
            {
                "location": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", "Invalid value."),
                "type": error.get("type", "value_error"),
            }
            for error in exc.errors()
        ]
    }
    return error_response(
        request.scope,
        status_code=422,
        code=ErrorCode.VALIDATION_ERROR,
        message="Request validation failed.",
        details=details,
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id, correlation_id = request_identifiers(request.scope)
    logger.exception(
        f"[REQUEST_ERROR] request_id={request_id} correlation_id={correlation_id} "
        f"method={request.method} path={request.url.path} error={type(exc).__name__}"
    )
    return error_response(
        request.scope,
        status_code=500,
        code=ErrorCode.INTERNAL_ERROR,
        message="An internal error occurred.",
    )


def _http_exception_message(detail: Any) -> str:
    if isinstance(detail, str) and detail.strip():
        return detail.strip()
    if isinstance(detail, dict):
        message = detail.get("message") or detail.get("detail")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return "The request could not be completed."
