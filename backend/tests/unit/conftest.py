from datetime import UTC, datetime, timedelta

import pytest

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
MICRO = timedelta(microseconds=1)


@pytest.fixture
def t0() -> datetime:
    return T0
