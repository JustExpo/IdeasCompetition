from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

T0 = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
MICRO = timedelta(microseconds=1)


@pytest.fixture
def t0() -> datetime:
    return T0


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Всё из tests/unit получает маркер unit: `pytest -m unit` берёт тесты без БД и сети."""
    unit_dir = Path(__file__).parent
    for item in items:
        if unit_dir in item.path.parents:
            item.add_marker(pytest.mark.unit)
