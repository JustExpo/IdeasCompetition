"""Конкурс в момент просмотра: фаза и доступные действия для конкретного пользователя."""

from dataclasses import dataclass
from datetime import datetime

from app.common.model import Actor, require_aware
from app.contest.model.contest import Contest, ContestPhase
from app.contest.model.policy import ContestAction, allowed_actions


@dataclass(frozen=True, slots=True)
class ContestDetails:
    """Карточка конкурса. `server_time` нужен клиенту, чтобы не доверять своим часам (П1, П2)."""

    contest: Contest
    phase: ContestPhase
    server_time: datetime
    actions: frozenset[ContestAction]

    def __post_init__(self) -> None:
        require_aware(self.server_time, "server_time")

    @classmethod
    def at(cls, contest: Contest, actor: Actor, now: datetime) -> "ContestDetails":
        phase = contest.phase_at(now)
        return cls(contest, phase, now, allowed_actions(actor, phase))
