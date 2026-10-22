"""Конкурс, его расписание и фаза."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from app.common.model import (
    MULTILINE_ALLOWED,
    ContestId,
    IdeaId,
    UserId,
    has_forbidden_chars,
    normalize_text,
    require_aware,
)
from app.contest.exception import DeadlinesOrderError, InvalidContestError

TOPIC_MAX_LENGTH = 200
DESCRIPTION_MAX_LENGTH = 10_000
# Правило ничьей показывается на странице конкурса с фазы подачи (П10): оно должно быть
# известно участникам до того, как они подадут идеи и проголосуют. Порядок — `rank_ideas`.
TIE_BREAK_RULE_TEXT = (
    "Побеждает идея с наибольшим числом голосов. При равенстве голосов побеждает идея, "
    "поданная раньше."
)


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
            raise DeadlinesOrderError("Голосование должно закрываться позже, чем приём идей")

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


def ensure_contest_text_valid(topic: str, description: str) -> None:
    """Инварианты темы и описания; общие для нового и сохранённого конкурса."""
    if not topic.strip() or len(topic) > TOPIC_MAX_LENGTH:
        raise InvalidContestError(f"Тема конкурса: от 1 до {TOPIC_MAX_LENGTH} символов")
    if len(description) > DESCRIPTION_MAX_LENGTH:
        raise InvalidContestError(f"Описание конкурса: не больше {DESCRIPTION_MAX_LENGTH} символов")
    if has_forbidden_chars(topic) or has_forbidden_chars(description, MULTILINE_ALLOWED):
        raise InvalidContestError("Тема или описание содержат недопустимые символы")


@dataclass(frozen=True, slots=True)
class NewContest:
    """Данные нового конкурса после нормализации и проверки (ещё без идентификатора)."""

    topic: str
    description: str
    schedule: ContestSchedule

    @classmethod
    def create(
        cls,
        topic: str,
        description: str,
        submission_deadline: datetime,
        voting_deadline: datetime,
    ) -> "NewContest":
        """Единственный способ получить `NewContest` из ввода: нормализует текст, проверяет всё."""
        topic = normalize_text(topic)
        description = normalize_text(description)
        ensure_contest_text_valid(topic, description)
        # Все моменты хранятся и отдаются в UTC: ответ на создание не должен отличаться от
        # последующих чтений только потому, что клиент прислал дедлайн с другим смещением.
        require_aware(submission_deadline, "submission_deadline")
        require_aware(voting_deadline, "voting_deadline")
        schedule = ContestSchedule(
            submission_deadline.astimezone(UTC), voting_deadline.astimezone(UTC)
        )
        return cls(topic, description, schedule)


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
        ensure_contest_text_valid(self.topic, self.description)
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
