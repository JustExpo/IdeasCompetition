from datetime import UTC, datetime, timedelta

import pytest

from app.common.exception import DomainValidationError
from app.core.clock import Clock, SystemClock
from tests.fakes import FrozenClock
from tests.unit.conftest import T0


def test_system_clock_returns_aware_utc_and_does_not_go_back() -> None:
    clock = SystemClock()
    first = clock.now()
    second = clock.now()
    assert first.tzinfo is not None
    assert first.utcoffset() == timedelta(0)
    assert second >= first


def test_frozen_clock_stands_still_until_moved() -> None:
    clock = FrozenClock(T0)
    assert clock.now() == T0
    assert clock.now() == T0
    clock.advance(timedelta(hours=1))
    assert clock.now() == T0 + timedelta(hours=1)
    clock.set(T0)
    assert clock.now() == T0


def test_frozen_clock_rejects_naive_datetime() -> None:
    with pytest.raises(DomainValidationError):
        FrozenClock(datetime(2026, 11, 1, 12, 0))  # noqa: DTZ001 — проверяем именно naive
    clock = FrozenClock(T0)
    with pytest.raises(DomainValidationError):
        clock.set(datetime(2026, 11, 1, 12, 0))  # noqa: DTZ001


def test_both_clocks_satisfy_clock_protocol() -> None:
    clocks: list[Clock] = [SystemClock(), FrozenClock(datetime(2026, 1, 1, tzinfo=UTC))]
    assert all(c.now().tzinfo is not None for c in clocks)
