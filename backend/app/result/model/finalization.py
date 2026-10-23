"""Кому какое итоговое письмо уходит при финализации (Ф4)."""

from collections.abc import Collection
from dataclasses import dataclass

from app.common.model import UserId
from app.result.model.ranking import RankedIdea


@dataclass(frozen=True, slots=True)
class FinalRecipients:
    """Один человек — одно письмо.

    `winner` — автор победившей идеи («Вы победили», даже если он ещё и голосовал или у него
    есть другие идеи). `not_passed` — остальные авторы («Ваша идея не прошла»).
    `voters_only` — только голосовали: им письмо с итогами.
    """

    winner: UserId | None
    not_passed: tuple[UserId, ...]
    voters_only: tuple[UserId, ...]


def has_tie_for_first(ranking: tuple[RankedIdea, ...]) -> bool:
    """Первое место разыграно правилом ничьей: у второй идеи столько же голосов (П10)."""
    return len(ranking) > 1 and ranking[0].score.votes == ranking[1].score.votes


def select_final_recipients(
    ranking: tuple[RankedIdea, ...], voter_ids: Collection[UserId]
) -> FinalRecipients:
    """Нет идей — нет победителя и писем."""
    if not ranking:
        return FinalRecipients(winner=None, not_passed=(), voters_only=())
    winner = ranking[0].score.author_id
    authors = {item.score.author_id for item in ranking}
    return FinalRecipients(
        winner=winner,
        not_passed=tuple(sorted(authors - {winner})),
        voters_only=tuple(sorted(set(voter_ids) - authors)),
    )
