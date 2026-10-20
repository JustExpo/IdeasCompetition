"""Нормализация и проверка пользовательского текста (темы, названия, описания)."""

import unicodedata

# Cc — управляющие, Cf — невидимые форматирующие (в т. ч. U+202E, которым
# переворачивают текст), Cs — одиночные суррогаты. В тексте пользователя не нужны.
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Cs"})
MULTILINE_ALLOWED = frozenset("\n\t")


def normalize_text(text: str) -> str:
    """NFC и обрезка пробелов по краям: «одинаковые» строки становятся равными посимвольно."""
    return unicodedata.normalize("NFC", text).strip()


def has_forbidden_chars(text: str, allowed: frozenset[str] = frozenset()) -> bool:
    return any(
        unicodedata.category(char) in _FORBIDDEN_CATEGORIES and char not in allowed for char in text
    )
