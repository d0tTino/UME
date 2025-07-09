import time
import types
import pytest

from ume.memory_aging import (
    start_vector_age_scheduler,
    stop_vector_age_scheduler,
    _check_stale_vectors,
)
from ume.config import settings
from ume.metrics import STALE_VECTOR_WARNINGS, STALE_VECTOR_COUNT


def test_vector_age_scheduler_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    now = int(time.time())
    store = types.SimpleNamespace(get_vector_timestamps=lambda: {"old": now - 100})

    monkeypatch.setattr(settings, "UME_VECTOR_MAX_AGE_DAYS", 0)
    STALE_VECTOR_WARNINGS._value.set(0)  # type: ignore[attr-defined]
    STALE_VECTOR_COUNT.set(0)

    thread, stop = start_vector_age_scheduler(store, interval_seconds=0.01, log=True)
    time.sleep(0.02)
    stop()
    stop_vector_age_scheduler()

    assert STALE_VECTOR_WARNINGS._value.get() == 1  # type: ignore[attr-defined]
    assert STALE_VECTOR_COUNT._value.get() == 1


def test_check_stale_vectors_updates_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct calls update stale vector metrics."""
    now = int(time.time())
    store = types.SimpleNamespace(get_vector_timestamps=lambda: {"old": now - 100})

    monkeypatch.setattr(settings, "UME_VECTOR_MAX_AGE_DAYS", 0)
    STALE_VECTOR_WARNINGS._value.set(0)  # type: ignore[attr-defined]
    STALE_VECTOR_COUNT.set(0)

    _check_stale_vectors(store, warn_threshold=0, log=True)

    assert STALE_VECTOR_WARNINGS._value.get() == 1  # type: ignore[attr-defined]
    assert STALE_VECTOR_COUNT._value.get() == 1

