"""Конкурс, его расписание и фаза."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.common.model import (
    MULTILINE_ALLOWED,
    ContestId,
    IdeaId,
    UserId,
    has_forbidden_chars,
    require_aware,
)
from app.contest.exception import InvalidContestError

TOPIC_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 10_000


class ContestPhase(StrEnum):
    """Фаза не хранится в БД, а вычисляется из времени: закрытию раунда нечему «не сработать»."""

    SUBMISSION = "submission"  # приём идей
    VOTING = "voting"  # голосование
    FINISHED = "finished"  # итоги видны всем


class ContestRound(StrEnum):
    """Раунд, по окончании которого рассылаются напоминания."""

    SUBMISSION = "submission"
    VOTING = "voting"


@dataclass(frozen=True, slots=True)
class ContestSchedule:
    """Два дедлайна конкурса. Раунд открыт, пока now < deadline (сам дедлайн уже закрыт)."""

    submission_deadline: datetime
    voting_deadline: datetime

    def __post_init__(self) -> None:
        require_aware(self.submission_deadline, "submission_deadline")
        require_aware(self.voting_deadline, "voting_deadline")
        if self.submission_deadline >= self.voting_deadline:
            raise InvalidContestError("Голосование должно закрываться позже, чем приём идей")

    def phase_at(self, now: datetime) -> ContestPhase:
        require_aware(now, "now")
        if now < self.submission_deadline:
            return ContestPhase.SUBMISSION
        if now < self.voting_deadline:
            return ContestPhase.VOTING
        return ContestPhase.FINISHED

    def round_deadline(self, contest_round: ContestRound) -> datetime:
        if contest_round is ContestRound.SUBMISSION:
            return self.submission_deadline
        return self.voting_deadline


@dataclass(frozen=True, slots=True)
class Contest:
    """Конкурс идей. Дедлайны неизменяемы после создания (CLAUDE.md, Р13)."""

    id: ContestId
    topic: str
    description: str
    schedule: ContestSchedule
    created_by: UserId
    created_at: datetime
    finalized_at: datetime | None = None
    winner_idea_id: IdeaId | None = None

    def __post_init__(self) -> None:
        require_aware(self.created_at, "created_at")
        # Текст приходит уже нормализованным (normalize_text в сервисе); здесь — инварианты.
        if not self.topic.strip() or len(self.topic) > TOPIC_MAX_LENGTH:
            raise InvalidContestError(f"Тема конкурса: от 1 до {TOPIC_MAX_LENGTH} символов")
        if len(self.description) > DESCRIPTION_MAX_LENGTH:
            raise InvalidContestError(
                f"Описание конкурса: не больше {DESCRIPTION_MAX_LENGTH} символов"
            )
        if has_forbidden_chars(self.topic) or has_forbidden_chars(
            self.description, MULTILINE_ALLOWED
        ):
            raise InvalidContestError("Тема или описание содержат недопустимые символы")
        if self.finalized_at is not None:
            require_aware(self.finalized_at, "finalized_at")
        if self.winner_idea_id is not None and self.finalized_at is None:
            raise InvalidContestError("Победитель известен только после финализации")

    def phase_at(self, now: datetime) -> ContestPhase:
        return self.schedule.phase_at(now)

    @property
    def is_finalized(self) -> bool:
        """Итог зафиксирован и письма поставлены в очередь (не то же самое, что фаза finished)."""
        return self.finalized_at is not None
