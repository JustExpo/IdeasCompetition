"""Правила регистрации и счётчики попыток без БД."""

import pytest

from app.auth.exception import TooManyLoginAttemptsError, TooManyRegistrationsError
from app.auth.service import AttemptLimiter
from app.user.exception import EmailDomainNotAllowedError, InvalidEmailError
from app.user.model import ensure_registration_valid

DOMAINS = ("example.com", "пример.рф")


def valid(**overrides: str) -> object:
    data = {"email": "a@example.com", "name": "Анна", "password": "p" * 10, **overrides}
    return ensure_registration_valid(allowed_domains=DOMAINS, **data)


def test_email_is_lowercased_and_trimmed() -> None:
    assert valid(email="  Anna@EXAMPLE.com ").email == "anna@example.com"  # type: ignore[attr-defined]


def test_idn_domain_matches_in_unicode_and_punycode() -> None:
    assert valid(email="a@ПРИМЕР.рф")
    assert valid(email="a@xn--e1afmkfd.xn--p1ai")


def test_foreign_domain_and_garbage_are_rejected() -> None:
    with pytest.raises(EmailDomainNotAllowedError):
        valid(email="a@evil.com")
    with pytest.raises(InvalidEmailError):
        valid(email="not-an-email")


def test_login_limit_blocks_after_five_failures_only() -> None:
    limiter = AttemptLimiter()
    for _ in range(5):
        limiter.ensure_login_allowed("a@example.com", "1.1.1.1")
        limiter.record_failed_login("a@example.com", "1.1.1.1")
    with pytest.raises(TooManyLoginAttemptsError):
        limiter.ensure_login_allowed("A@example.com", "1.1.1.1")
    limiter.ensure_login_allowed("a@example.com", "2.2.2.2")


def test_registration_limit_is_five_per_ip() -> None:
    limiter = AttemptLimiter()
    for _ in range(5):
        limiter.ensure_registration_allowed("1.1.1.1")
    with pytest.raises(TooManyRegistrationsError):
        limiter.ensure_registration_allowed("1.1.1.1")
    limiter.ensure_registration_allowed("2.2.2.2")


def test_without_per_ip_limit_registration_is_free_and_login_is_keyed_by_email() -> None:
    limiter = AttemptLimiter(per_ip_enabled=False)
    for _ in range(20):
        limiter.ensure_registration_allowed("1.1.1.1")
    for _ in range(5):
        limiter.record_failed_login("a@example.com", "1.1.1.1")
    with pytest.raises(TooManyLoginAttemptsError):
        limiter.ensure_login_allowed("a@example.com", "9.9.9.9")
