"""Напоминания за сутки до закрытия раунда тем, кто ещё не участвовал (П9)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId
from app.contest import service as contest_service
from app.contest.model import Contest, ContestPhase, ContestRound
from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.idea import service as idea_service
from app.notification import service as notification_service
from app.notification.model import EmailKind
from app.reminder import dao
from app.reminder.model import (
    REMINDER_LEAD_TIME,
    reminder_window_contains,
    select_reminder_recipients,
)
from app.user import service as user_service
from app.vote import service as vote_service

_log = get_logger(__name__)

_OPEN_PHASE = {
    ContestRound.SUBMISSION: ContestPhase.SUBMISSION,
    ContestRound.VOTING: ContestPhase.VOTING,
}
_KIND = {
    ContestRound.SUBMISSION: EmailKind.SUBMISSION_REMINDER,
    ContestRound.VOTING: EmailKind.VOTING_REMINDER,
}


async def _remind_round(
    database: Database,
    clock: Clock,
    contest_id: ContestId,
    contest_round: ContestRound,
    *,
    public_base_url: str,
    display_tz: str,
) -> int:
    """Одна транзакция на (конкурс, раунд): отметки и письма появляются вместе или не появляются."""

    async def work(session: AsyncSession) -> int:
        now = clock.now()
        contest: Contest = await contest_service.find_contest(session, contest_id)
        deadline = contest.schedule.round_deadline(contest_round)
        # Раунд должен быть открыт: напоминание «закроется завтра» о закрытом раунде бессмысленно,
        # а голосование, которое ещё не началось, голосовать не зовёт.
        if contest.phase_at(now) is not _OPEN_PHASE[contest_round]:
            return 0
        if not reminder_window_contains(deadline, now):
            return 0
        ideas = await idea_service.list_all_contest_ideas(session, contest_id)
        if contest_round is ContestRound.SUBMISSION:
            participants = {idea.author_id for idea in ideas}
        else:
            participants = set(await vote_service.list_voter_ids(session, [i.id for i in ideas]))
        employees = await user_service.list_active_employees(session)
        recipients = select_reminder_recipients((user.id for user in employees), participants)
        inserted = await dao.insert_reminders_if_absent(
            session, contest_id, contest_round, recipients, now
        )
        by_id = {user.id: user for user in employees}
        url = f"{public_base_url.rstrip('/')}/contests/{int(contest_id)}"
        render = (
            notification_service.render_submission_reminder
            if contest_round is ContestRound.SUBMISSION
            else notification_service.render_voting_reminder
        )
        mail = render(topic=contest.topic, deadline=deadline, display_tz=display_tz, url=url)
        for user_id in inserted:
            await notification_service.enqueue_email(
                session,
                kind=_KIND[contest_round],
                contest_id=contest_id,
                user_id=user_id,
                to_email=by_id[user_id].email,
                subject=mail.subject,
                body=mail.body,
                now=now,
                not_after=deadline,
            )
        return len(inserted)

    return await database.run_in_transaction(work)


async def enqueue_due_reminders(
    database: Database, clock: Clock, *, public_base_url: str, display_tz: str
) -> int:
    """Поставить напоминания всем конкурсам с раундом в окне «последние 24 часа».

    Возвращает число созданных напоминаний. Повтор и параллельный тик ничего не дублируют:
    это держит первичный ключ `reminders`, а не проверка в коде.
    """

    async def find_candidates(session: AsyncSession) -> list[tuple[ContestId, ContestRound]]:
        now = clock.now()
        found: list[tuple[ContestId, ContestRound]] = []
        for contest_round in ContestRound:
            contests = await contest_service.list_contests_in_reminder_window(
                session, contest_round, now, REMINDER_LEAD_TIME
            )
            found.extend((contest.id, contest_round) for contest in contests)
        return found

    created = 0
    for contest_id, contest_round in await database.run_in_transaction(find_candidates):
        count = await _remind_round(
            database,
            clock,
            contest_id,
            contest_round,
            public_base_url=public_base_url,
            display_tz=display_tz,
        )
        if count:
            _log.info(
                "reminders_enqueued",
                contest_id=int(contest_id),
                round=contest_round.value,
                count=count,
            )
        created += count
    return created
