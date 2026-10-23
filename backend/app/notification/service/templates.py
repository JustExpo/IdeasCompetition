"""Тексты писем (plain text). Данные приходят уже проверенными: тема конкурса и название идеи
не содержат управляющих символов (`common.model.text`), а заголовки собирает `EmailMessage`."""

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    body: str


def format_moment(moment: datetime, display_tz: str) -> str:
    """Момент в часовом поясе показа (`DISPLAY_TZ`), с названием пояса: «24.10.2026 15:00 (MSK)»."""
    local = moment.astimezone(ZoneInfo(display_tz))
    return f"{local:%d.%m.%Y %H:%M} ({local.tzname()})"


def render_winner_email(*, topic: str, idea_title: str, votes: int, url: str) -> RenderedEmail:
    return RenderedEmail(
        subject=f"Вы победили в конкурсе «{topic}»",
        body=(
            f"Поздравляем! Ваша идея «{idea_title}» победила в конкурсе «{topic}».\n"
            f"Голосов за неё: {votes}.\n\n"
            f"Итоги конкурса: {url}\n"
        ),
    )


def render_not_passed_email(
    *, topic: str, winner_title: str, tie_rule: str | None, url: str
) -> RenderedEmail:
    tie_note = f"\n{tie_rule}\n" if tie_rule else ""
    return RenderedEmail(
        subject=f"Ваша идея не прошла: конкурс «{topic}»",
        body=(
            f"Конкурс «{topic}» завершён. К сожалению, ваша идея не прошла.\n"
            f"Победила идея «{winner_title}».\n{tie_note}\n"
            f"Итоги конкурса: {url}\n"
        ),
    )


def render_results_email(*, topic: str, winner_title: str, url: str) -> RenderedEmail:
    return RenderedEmail(
        subject=f"Итоги конкурса «{topic}»",
        body=(
            f"Конкурс «{topic}» завершён. Спасибо, что приняли участие в голосовании.\n"
            f"Победила идея «{winner_title}».\n\n"
            f"Итоги конкурса: {url}\n"
        ),
    )


def render_submission_reminder(
    *, topic: str, deadline: datetime, display_tz: str, url: str
) -> RenderedEmail:
    return RenderedEmail(
        subject=f"Завтра закрывается приём идей: «{topic}»",
        body=(
            f"Приём идей в конкурсе «{topic}» закроется {format_moment(deadline, display_tz)}.\n"
            "Вы ещё не подали ни одной идеи.\n\n"
            f"Подать идею: {url}\n"
        ),
    )


def render_voting_reminder(
    *, topic: str, deadline: datetime, display_tz: str, url: str
) -> RenderedEmail:
    return RenderedEmail(
        subject=f"Завтра закрывается голосование: «{topic}»",
        body=(
            f"Голосование в конкурсе «{topic}» закроется {format_moment(deadline, display_tz)}.\n"
            "Вы ещё не проголосовали.\n\n"
            f"Проголосовать: {url}\n"
        ),
    )
