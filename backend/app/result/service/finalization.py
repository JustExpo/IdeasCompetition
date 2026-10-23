"""Финализация: после закрытия голосования фиксирует итог и ставит итоговые письма (Ф4)."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId, UserId
from app.contest import service as contest_service
from app.contest.model import TIE_BREAK_RULE_TEXT, Contest
from app.core.clock import Clock
from app.core.db import Database
from app.core.logging import get_logger
from app.notification import service as notification_service
from app.notification.model import EmailKind
from app.result.model import has_tie_for_first, select_final_recipients
from app.result.service.results import RankingSnapshot, rank_contest_ideas
from app.user import service as user_service

_log = get_logger(__name__)


def contest_url(public_base_url: str, contest_id: ContestId) -> str:
    return f"{public_base_url.rstrip('/')}/contests/{int(contest_id)}"


async def _enqueue_final_emails(
    session: AsyncSession,
    contest: Contest,
    snapshot: RankingSnapshot,
    *,
    now: datetime,
    public_base_url: str,
) -> None:
    winner_item = snapshot.ranking[0]
    recipients = select_final_recipients(snapshot.ranking, snapshot.voter_ids)
    wanted = [
        user_id
        for user_id in (recipients.winner, *recipients.not_passed, *recipients.voters_only)
        if user_id is not None
    ]
    users = await user_service.get_users(session, wanted)
    url = contest_url(public_base_url, contest.id)
    tie_rule = TIE_BREAK_RULE_TEXT if has_tie_for_first(snapshot.ranking) else None

    async def enqueue(user_id: UserId, kind: EmailKind, subject: str, body: str) -> None:
        user = users.get(user_id)
        if user is None or not user.is_active:
            return
        await notification_service.enqueue_email(
            session,
            kind=kind,
            contest_id=contest.id,
            user_id=user_id,
            to_email=user.email,
            subject=subject,
            body=body,
            now=now,
        )

    if recipients.winner is not None:
        winner_mail = notification_service.render_winner_email(
            topic=contest.topic,
            idea_title=winner_item.score.title,
            votes=winner_item.score.votes,
            url=url,
        )
        await enqueue(
            recipients.winner, EmailKind.WINNER_ANNOUNCEMENT, winner_mail.subject, winner_mail.body
        )
    not_passed_mail = notification_service.render_not_passed_email(
        topic=contest.topic, winner_title=winner_item.score.title, tie_rule=tie_rule, url=url
    )
    for user_id in recipients.not_passed:
        await enqueue(
            user_id, EmailKind.RESULTS_ANNOUNCEMENT, not_passed_mail.subject, not_passed_mail.body
        )
    results_mail = notification_service.render_results_email(
        topic=contest.topic, winner_title=winner_item.score.title, url=url
    )
    for user_id in recipients.voters_only:
        await enqueue(
            user_id, EmailKind.RESULTS_ANNOUNCEMENT, results_mail.subject, results_mail.body
        )


async def finalize_contest(
    database: Database, clock: Clock, contest_id: ContestId, *, public_base_url: str
) -> bool:
    """Зафиксировать итог одного конкурса и поставить письма в одной транзакции.

    `contest FOR UPDATE` дожидается всех записей, начатых до дедлайна (они держат `FOR SHARE`):
    голос, принятый до `voting_deadline`, попадает в итог, поздний получает 409 (Р6).
    Возвращает `False`, если делать нечего: итог уже зафиксирован или время ещё не пришло.
    """

    async def work(session: AsyncSession) -> bool:
        contest = await contest_service.lock_contest_for_finalization(session, contest_id)
        now = clock.now()
        if contest.is_finalized or now < contest.schedule.voting_deadline:
            return False
        snapshot = await rank_contest_ideas(session, contest_id)
        winner = snapshot.ranking[0].score.idea_id if snapshot.ranking else None
        if not await contest_service.record_finalization(
            session, contest_id, now=now, winner=winner
        ):
            return False
        if snapshot.ranking:
            await _enqueue_final_emails(
                session, contest, snapshot, now=now, public_base_url=public_base_url
            )
        return True

    return await database.run_in_transaction(work)


async def finalize_due_contests(
    database: Database, clock: Clock, *, public_base_url: str
) -> list[ContestId]:
    """Финализировать все конкурсы с закрытым голосованием. Повторный вызов ничего не меняет.

    Конкурсы обрабатываются каждый в своей транзакции: сбой одного не откатывает остальные
    и на следующем тике будет повторён.
    """

    async def find_due(session: AsyncSession) -> list[ContestId]:
        return await contest_service.list_unfinalized_contest_ids(session, clock.now())

    finalized: list[ContestId] = []
    for contest_id in await database.run_in_transaction(find_due):
        if await finalize_contest(database, clock, contest_id, public_base_url=public_base_url):
            finalized.append(contest_id)
            _log.info("contest_finalized", contest_id=int(contest_id))
    return finalized
