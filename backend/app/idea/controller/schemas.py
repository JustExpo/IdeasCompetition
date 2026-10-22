"""Схемы запросов и ответов подачи и правки идеи."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.idea.model import Idea


class SubmitIdeaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Верхние пределы — защита от гигантских значений; точные длины проверяет idea.model.
    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1, max_length=50_000)
    # Ключ повтора генерирует SPA при открытии формы: повтор после обрыва не создаёт дубль (§8.3).
    client_request_id: UUID


class EditIdeaRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=1000)
    description: str = Field(min_length=1, max_length=50_000)
    # Версия, на которую опиралась форма: защита от потерянных правок из двух вкладок.
    version: int = Field(ge=1)


class IdeaResponse(BaseModel):
    """Своя идея автора: автор знает, что она его, поэтому время подачи и версия показываются."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    contest_id: int
    title: str
    description: str
    version: int
    submitted_at: datetime
    updated_at: datetime

    @classmethod
    def from_idea(cls, idea: Idea) -> "IdeaResponse":
        return cls(
            id=idea.id,
            contest_id=idea.contest_id,
            title=idea.content.title,
            description=idea.content.description,
            version=idea.version,
            submitted_at=idea.submitted_at,
            updated_at=idea.updated_at,
        )
