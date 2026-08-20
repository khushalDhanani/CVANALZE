from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("cv_analyzer")


class DegradationMode(str, Enum):
    NONE = "NONE"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    CACHED_VACANCY_SNAPSHOT = "CACHED_VACANCY_SNAPSHOT"
    LEXICAL_ONLY_RETRIEVAL = "LEXICAL_ONLY_RETRIEVAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class DegradationReport:
    mode: DegradationMode = DegradationMode.NONE
    is_degraded: bool = False
    quality_flags: list[str] = field(default_factory=list)
    trigger_reason: str | None = None
    created_at: float = field(default_factory=time.time)

    def add_flag(self, flag: str) -> None:
        if flag not in self.quality_flags:
            self.quality_flags.append(flag)
            self.is_degraded = True


class DegradationEngine:
    """
    Typed Degradation Engine.
    Handles controlled, observable fallback execution paths during partial infrastructure outages.
    Guarantees deterministic operation and structured quality flagging without unhandled 500 crashes.
    """

    @staticmethod
    def create_report(
        mode: DegradationMode = DegradationMode.NONE,
        trigger_reason: str | None = None,
        initial_flags: list[str] | None = None,
    ) -> DegradationReport:
        is_deg = mode != DegradationMode.NONE
        flags = list(initial_flags or [])
        if is_deg and mode == DegradationMode.DETERMINISTIC_FALLBACK:
            flags.append("LLM_UNAVAILABLE_FALLBACK")
        elif is_deg and mode == DegradationMode.CACHED_VACANCY_SNAPSHOT:
            flags.append("STALE_VACANCY_SNAPSHOT")
        elif is_deg and mode == DegradationMode.LEXICAL_ONLY_RETRIEVAL:
            flags.append("VECTOR_SERVICE_FALLBACK")

        if is_deg:
            logger.warning(
                f"[DEGRADATION_ENGINE] Active mode: {mode.value} | reason: {trigger_reason or 'Infrastructure condition'} | flags: {flags}"
            )

        return DegradationReport(
            mode=mode,
            is_degraded=is_deg,
            quality_flags=flags,
            trigger_reason=trigger_reason,
        )
