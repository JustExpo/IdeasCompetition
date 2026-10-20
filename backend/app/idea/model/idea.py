"""Идея конкурса и правила её текста."""

from dataclasses import dataclass, field
from datetime import datetime

from app.common.exception import DomainValidationError
from app.common.model import (
    MULTILINE_ALLOWED,
    ContestId,
    IdeaId,
    UserId,
    has_forbidden_chars,
    normalize_text,
    require_aware,
)
from app.idea.exception import InvalidIdeaContentError

TITLE_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 10_000
# Лимиты мягкие: параллельная подача может превысить их на единицы (CLAUDE.md §7.2).
IDEAS_PER_AUTHOR_LIMIT = 20
IDEAS_PER_CONTEST_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class IdeaContent:
    """Название и описание идеи после нормализации (NFC, без пробелов по краям).

    Текст скрыт из repr: тексты идей не пишутся в логи (CLAUDE.md §13).
    """

    title: str = field(repr=False)
    description: str = field(repr=False)

    @classmethod
    def create(cls, title: str, description: str) -> "IdeaContent":
        """Нормализует ввод и проверяет его; единственный способ получить IdeaContent из ввода."""
        return cls(title=normalize_text(title), description=normalize_text(description))

    def __post_init__(self) -> None:
        if not self.title or len(self.title) > TITLE_MAX_LENGTH:
            raise InvalidIdeaContentError(f"Название: от 1 до {TITLE_MAX_LENGTH} символов")
        if not self.description or len(self.description) > DESCRIPTION_MAX_LENGTH:
            raise InvalidIdeaContentError(f"Описание: от 1 до {DESCRIPTION_MAX_LENGTH} символов")
        if has_forbidden_chars(self.title):
            raise InvalidIdeaContentError("Название содержит недопустимые символы")
        if has_forbidden_chars(self.description, MULTILINE_ALLOWED):
            raise InvalidIdeaContentError("Описание содержит недопустимые символы")


@dataclass(frozen=True, slots=True)
class Idea:
    """Идея сотрудника.

    `submitted_at` ставится один раз при подаче и не меняется при правке: по нему
    решается ничья (П10). `version` растёт при каждой правке и защищает от
    потерянных изменений из двух вкладок. Автор скрыт из repr: связка автор ↔ идея
    до финала не должна попадать в логи.
    """

    id: IdeaId
    contest_id: ContestId
    author_id: UserId = field(repr=False)
    content: IdeaContent
    submitted_at: datetime
    updated_at: datetime
    version: int = 1

    def __post_init__(self) -> None:
        require_aware(self.submitted_at, "submitted_at")
        require_aware(self.updated_at, "updated_at")
        if self.updated_at < self.submitted_at:
            raise DomainValidationError("Время правки не может быть раньше подачи")
        if self.version < 1:
            raise DomainValidationError("Версия идеи начинается с 1")

    def is_authored_by(self, user_id: UserId) -> bool:
        return self.author_id == user_id
