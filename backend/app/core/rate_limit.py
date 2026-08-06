from __future__ import annotations
import threading
import time
from collections import deque
from dataclasses import dataclass

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import settings
from app.core.error_handlers import error_response
from app.schemas.contracts import ErrorCode


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    reset_after_seconds: int


class InMemoryRateLimiter:
    """Thread-safe per-process sliding-window limiter for the application boundary."""

    def __init__(self):
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, identifier: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        now = time.monotonic()
        safe_limit = max(1, limit)
        safe_window = max(1, window_seconds)
        cutoff = now - safe_window
        with self._lock:
            events = self._events.setdefault(identifier, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= safe_limit:
                reset_after = max(1, int(events[0] + safe_window - now) + 1)
                return RateLimitDecision(False, 0, reset_after)
            events.append(now)
            remaining = max(0, safe_limit - len(events))
            self._trim_buckets()
            return RateLimitDecision(True, remaining, safe_window)

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def _trim_buckets(self) -> None:
        maximum = max(1, settings.RATE_LIMIT_MAX_BUCKETS)
        while len(self._events) > maximum:
            self._events.pop(next(iter(self._events)), None)


class RateLimitMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app
        self.limiter = InMemoryRateLimiter()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if not settings.RATE_LIMIT_ENABLED or scope["type"] not in (
            "http",
            "websocket",
        ):
            await self.app(scope, receive, send)
            return
        if scope.get("method") == "OPTIONS" or scope.get("path") in ("/", "/health"):
            await self.app(scope, receive, send)
            return

        decision = self.limiter.check(
            _request_identifier(scope),
            limit=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
        )
        if not decision.allowed:
            if scope["type"] == "websocket":
                await send(
                    {
                        "type": "websocket.close",
                        "code": 4429,
                        "reason": "Rate limit exceeded.",
                    }
                )
                return
            response = error_response(
                scope,
                status_code=429,
                code=ErrorCode.RATE_LIMITED,
                message="Rate limit exceeded.",
                retryable=True,
                headers={
                    "Retry-After": str(decision.reset_after_seconds),
                    "X-RateLimit-Limit": str(max(1, settings.RATE_LIMIT_REQUESTS)),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(decision.reset_after_seconds),
                },
            )
            await response(scope, receive, send)
            return

        async def send_with_limits(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-RateLimit-Limit"] = str(max(1, settings.RATE_LIMIT_REQUESTS))
                headers["X-RateLimit-Remaining"] = str(decision.remaining)
                headers["X-RateLimit-Reset"] = str(decision.reset_after_seconds)
            await send(message)

        await self.app(scope, receive, send_with_limits)


def _request_identifier(scope: Scope) -> str:
    client = scope.get("client")
    address = client[0] if client else "unknown"
    return f"client:{address}"
