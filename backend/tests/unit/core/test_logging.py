import io
import json
import logging
from collections.abc import Iterator

import pytest
import structlog

from app.core.logging import (
    REDACTED,
    bind_log_context,
    clear_log_context,
    configure_logging,
    get_logger,
    mask_email,
    mask_emails_in_text,
    shutdown_logging,
)

EMAIL = "alice.smith@example.com"
PASSWORD = "p4ssw0rd-very-secret"  # gitleaks:allow — фиктивное значение для проверки маскирования


@pytest.fixture
def stream() -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    configure_logging(level="INFO", fmt="json", stream=buffer)
    yield buffer
    clear_log_context()
    shutdown_logging()
    structlog.reset_defaults()


def lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


@pytest.mark.parametrize(
    ("raw", "masked"),
    [
        ("alice@example.com", "a***@example.com"),
        ("a@d.com", "a***@d.com"),
        ("Боб@example.com", "Б***@example.com"),
    ],
)
def test_mask_email_keeps_first_letter_and_domain(raw: str, masked: str) -> None:
    assert mask_email(raw) == masked


def test_mask_emails_in_text_handles_several_addresses() -> None:
    text = "от bob@corp.org к eve+tag@mail.example.com, без адреса ничего не меняем"
    assert mask_emails_in_text(text) == (
        "от b***@corp.org к e***@mail.example.com, без адреса ничего не меняем"
    )


def test_record_is_json_with_ts_level_event_and_bound_context(stream: io.StringIO) -> None:
    bind_log_context(request_id="req-1", user_id=7)
    get_logger("app.test").info("vote_cast", contest_id=3)
    (record,) = lines(stream)
    assert record["event"] == "vote_cast"
    assert record["level"] == "info"
    assert record["request_id"] == "req-1"
    assert record["user_id"] == 7
    assert record["contest_id"] == 3
    assert str(record["ts"]).endswith("Z")


def test_context_is_cleared_between_requests(stream: io.StringIO) -> None:
    bind_log_context(request_id="req-1")
    clear_log_context()
    get_logger("app.test").info("after")
    assert "request_id" not in lines(stream)[0]


def test_email_in_value_and_message_is_masked(stream: io.StringIO) -> None:
    get_logger("app.test").info(f"login failed for {EMAIL}", email=EMAIL, extra={"to": [EMAIL]})
    raw = stream.getvalue()
    assert EMAIL not in raw
    (record,) = lines(stream)
    assert record["email"] == "a***@example.com"
    assert record["extra"] == {"to": ["a***@example.com"]}


@pytest.mark.parametrize(
    "key", ["password", "Password", "token", "cookie", "authorization", "sid", "title", "body"]
)
def test_sensitive_keys_are_redacted(stream: io.StringIO, key: str) -> None:
    get_logger("app.test").info("event", **{key: PASSWORD})
    assert PASSWORD not in stream.getvalue()
    assert lines(stream)[0][key] == REDACTED


def test_nested_sensitive_keys_are_redacted(stream: io.StringIO) -> None:
    get_logger("app.test").info("event", payload={"user": {"password": PASSWORD, "id": 1}})
    assert PASSWORD not in stream.getvalue()
    assert lines(stream)[0]["payload"] == {"user": {"password": REDACTED, "id": 1}}


def test_secret_str_never_prints_value(stream: io.StringIO) -> None:
    from pydantic import SecretStr

    get_logger("app.test").info("event", dsn=SecretStr(PASSWORD))
    assert PASSWORD not in stream.getvalue()


def test_exception_text_is_masked(stream: io.StringIO) -> None:
    try:
        raise ValueError(f"нет пользователя {EMAIL}")
    except ValueError:
        get_logger("app.test").exception("failed")
    raw = stream.getvalue()
    assert EMAIL not in raw
    assert "a***@example.com" in raw


def test_standard_library_loggers_go_through_same_chain(stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.error").warning("bad request from %s", EMAIL)
    (record,) = lines(stream)
    assert record["level"] == "warning"
    assert EMAIL not in stream.getvalue()
    assert "a***@example.com" in str(record["event"])


def test_level_filters_lower_records(stream: io.StringIO) -> None:
    get_logger("app.test").debug("hidden")
    get_logger("app.test").info("shown")
    assert [r["event"] for r in lines(stream)] == ["shown"]


def test_reconfigure_replaces_handler_instead_of_duplicating(stream: io.StringIO) -> None:
    second = io.StringIO()
    configure_logging(level="INFO", fmt="json", stream=second)
    get_logger("app.test").info("once")
    assert stream.getvalue() == ""
    assert len(lines(second)) == 1


def test_console_format_still_masks(stream: io.StringIO) -> None:
    console = io.StringIO()
    configure_logging(level="INFO", fmt="console", stream=console)
    get_logger("app.test").info("login", email=EMAIL, password=PASSWORD)
    assert EMAIL not in console.getvalue()
    assert PASSWORD not in console.getvalue()


def test_caplog_sees_no_password_or_full_email(
    stream: io.StringIO, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        get_logger("app.test").info("login", email=EMAIL, password=PASSWORD)
    assert "login" in caplog.text
    assert EMAIL not in caplog.text
    assert PASSWORD not in caplog.text
