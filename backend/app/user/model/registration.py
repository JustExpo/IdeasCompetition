"""Правила регистрации сотрудника: адрес, домен, имя, пароль (CLAUDE.md §9.1)."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final

from email_validator import EmailNotValidError, validate_email

from app.common.model import has_forbidden_chars, is_password_length_valid, normalize_text
from app.user.exception import (
    EmailDomainNotAllowedError,
    InvalidEmailError,
    InvalidNameError,
    InvalidPasswordError,
)
from app.user.model.user import normalize_email

USER_NAME_MAX_LENGTH: Final = 100  # в БД предел шире (200): запас на будущие правила


@dataclass(frozen=True, slots=True)
class Registration:
    """Проверенные данные для создания учётной записи (пароль сюда не входит)."""

    email: str
    name: str


def _to_ascii_domain(domain: str) -> str:
    try:
        return domain.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return domain.lower()


def ensure_registration_valid(
    *, email: str, name: str, password: str, allowed_domains: Iterable[str]
) -> Registration:
    """Проверить данные регистрации и привести адрес и имя к каноническому виду.

    Домен сравнивается в ASCII-форме (punycode), поэтому «пример.рф» и «xn--e1afmkfd.xn--p1ai»
    считаются одним доменом. Подтверждение адреса вне объёма (Р11): проверяется только форма.
    """
    try:
        parsed = validate_email(email.strip(), check_deliverability=False)
    except EmailNotValidError as error:
        raise InvalidEmailError("Укажите корректный адрес электронной почты.") from error
    if _to_ascii_domain(parsed.domain) not in {_to_ascii_domain(d) for d in allowed_domains}:
        raise EmailDomainNotAllowedError("Регистрация доступна только для адресов компании.")

    clean_name = normalize_text(name)
    if not 1 <= len(clean_name) <= USER_NAME_MAX_LENGTH or has_forbidden_chars(clean_name):
        raise InvalidNameError(f"Имя должно быть от 1 до {USER_NAME_MAX_LENGTH} символов.")
    if not is_password_length_valid(password):
        raise InvalidPasswordError("Пароль должен быть от 10 до 128 символов.")
    return Registration(email=normalize_email(parsed.normalized), name=clean_name)
