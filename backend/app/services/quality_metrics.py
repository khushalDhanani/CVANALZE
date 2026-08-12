from __future__ import annotations

import threading
from collections import Counter
from typing import Any


class QualityMetrics:
    """Process-local operational counters; durable request-level detail lives in LLM execution traces."""

    _lock = threading.Lock()
    _counts: Counter[str] = Counter()
    _values: Counter[str] = Counter()

    @classmethod
    def record(cls, category: str, **values: int | float | bool) -> None:
        with cls._lock:
            cls._counts[category] += 1
            for name, value in values.items():
                cls._values[f"{category}.{name}"] += float(value)

    @classmethod
    def report(cls) -> dict[str, Any]:
        with cls._lock:
            categories: dict[str, Any] = {}
            for category, events in sorted(cls._counts.items()):
                totals = {
                    key.split(".", 1)[1]: round(value, 4)
                    for key, value in cls._values.items()
                    if key.startswith(f"{category}.")
                }
                categories[category] = {"events": events, "totals": totals}
            return categories

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._counts.clear()
            cls._values.clear()
