"""Чистые части `app.core.db` и защита integration-тестов от нетестовой БД."""

import pytest
from sqlalchemy import exc as sa_exc

from app.core.db import (
    NAMING_CONVENTION,
    Base,
    describe_schema_mismatch,
    expected_schema_revision,
    is_database_unavailable,
    is_retryable_conflict,
)
from tests.integration.database import ensure_test_database_url


class FakePostgresError(Exception):
    def __init__(self, sqlstate: str) -> None:
        super().__init__(sqlstate)
        self.sqlstate = sqlstate


def driver_error(sqlstate: str) -> sa_exc.DBAPIError:
    return sa_exc.DBAPIError("SELECT 1", {}, FakePostgresError(sqlstate))


@pytest.mark.parametrize("sqlstate", ["40P01", "40001"])
def test_deadlock_and_serialization_failure_are_retryable(sqlstate: str) -> None:
    assert is_retryable_conflict(driver_error(sqlstate))


@pytest.mark.parametrize("error", [driver_error("23505"), ValueError("x"), KeyError("y")])
def test_other_errors_are_not_retryable(error: BaseException) -> None:
    assert not is_retryable_conflict(error)


@pytest.mark.parametrize("sqlstate", ["08006", "08001", "57P01", "57P03", "55P03", "57014"])
def test_connection_loss_and_timeouts_mean_unavailable(sqlstate: str) -> None:
    assert is_database_unavailable(driver_error(sqlstate))


@pytest.mark.parametrize(
    "error", [ConnectionRefusedError(), TimeoutError(), sa_exc.TimeoutError("pool")]
)
def test_network_and_pool_errors_mean_unavailable(error: BaseException) -> None:
    assert is_database_unavailable(error)


@pytest.mark.parametrize(
    "error", [driver_error("23505"), driver_error("28P01"), ValueError("x"), driver_error("40P01")]
)
def test_constraint_auth_and_logic_errors_are_not_unavailability(error: BaseException) -> None:
    assert not is_database_unavailable(error)


def test_expected_revision_is_the_only_head() -> None:
    assert expected_schema_revision() == "0001"


def test_matching_revision_has_no_message() -> None:
    assert describe_schema_mismatch("0001", "0001") is None


def test_unknown_revision_message_names_both_revisions() -> None:
    assert (
        describe_schema_mismatch("zzzz", "0001") == "БД на ревизии zzzz, приложению известна 0001."
    )


def test_missing_version_table_asks_for_migrations() -> None:
    message = describe_schema_mismatch(None, "0001")

    assert message is not None
    assert "alembic upgrade head" in message


def test_naming_convention_is_attached_to_base_metadata() -> None:
    assert Base.metadata.naming_convention == NAMING_CONVENTION


@pytest.mark.parametrize(
    "url", ["postgresql+asyncpg://u:p@h:5433/ideas_test", "postgresql://h/x_test"]
)
def test_test_database_names_are_accepted(url: str) -> None:
    assert ensure_test_database_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+asyncpg://u:p@h/ideas",
        "postgresql+asyncpg://u:p@h/ideas_e2e",
        "postgresql+asyncpg://u:p@h/ideas_test_backup",
        "postgresql+asyncpg://u:p@h/",
    ],
)
def test_non_test_database_is_refused(url: str) -> None:
    with pytest.raises(RuntimeError, match="_test"):
        ensure_test_database_url(url)
