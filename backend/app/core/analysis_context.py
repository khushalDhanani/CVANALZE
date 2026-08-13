from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar, Token
from uuid import uuid4


_analysis_run_id: ContextVar[str] = ContextVar("analysis_run_id", default="not_available")
_analysis_candidate: ContextVar[str] = ContextVar("analysis_candidate", default="not_available")


def new_analysis_run_id() -> str:
    return f"analysis_{uuid4().hex}"


def get_analysis_run_id() -> str:
    return _analysis_run_id.get()


def get_analysis_candidate() -> str:
    return _analysis_candidate.get()


def set_analysis_run_id(analysis_run_id: str | None) -> Token[str]:
    return _analysis_run_id.set(str(analysis_run_id or "not_available"))


@contextmanager
def analysis_run_context(analysis_run_id: str, candidate: str | None = None) -> Iterator[None]:
    run_token = set_analysis_run_id(analysis_run_id)
    candidate_token = _analysis_candidate.set(str(candidate or "not_available"))
    try:
        yield
    finally:
        _analysis_candidate.reset(candidate_token)
        _analysis_run_id.reset(run_token)


@asynccontextmanager
async def async_analysis_run_context(analysis_run_id: str, candidate: str | None = None) -> AsyncIterator[None]:
    with analysis_run_context(analysis_run_id, candidate):
        yield
