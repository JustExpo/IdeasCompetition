"""Правила пароля, общие для настроек (пароль организатора) и входа/регистрации."""

import unicodedata
from typing import Final

PASSWORD_MIN_LENGTH: Final = 10
PASSWORD_MAX_LENGTH: Final = 128


def normalize_password(password: str) -> str:
    """NFKC перед хэшированием: один и тот же пароль, набранный разными раскладками Unicode,
    даёт один хэш (CLAUDE.md §9.1)."""
    return unicodedata.normalize("NFKC", password)


def is_password_length_valid(password: str) -> bool:
    """Длина считается по нормализованному паролю, в символах Unicode."""
    return PASSWORD_MIN_LENGTH <= len(normalize_password(password)) <= PASSWORD_MAX_LENGTH
