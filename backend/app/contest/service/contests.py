"""Сценарии конкурсов: создание, список, карточка (CLAUDE.md §8.2)."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import Actor, ContestId
from app.contest import dao
from app.contest.exception import ContestNotFoundError, DeadlineInPastError
from app.contest.model import Contest, ContestDetails, ContestPhase, NewContest
from app.core.clock import Clock
from app.core.db import Database

LIST_LIMIT_MAX = 100


@dataclass(frozen=True, slots=True)
class ContestsPage:
    """Страница списка: у каждого конкурса фаза на момент `server_time`."""

    items: tuple[tuple[Contest, ContestPhase], ...]
    total: int
    server_time: datetime


async def create_contest(
    database: Database,
    clock: Clock,
    actor: Actor,
    *,
    topic: str,
    description: str,
    submission_deadline: datetime,
    voting_deadline: datetime,
) -> ContestDetails:
    """Создать конкурс. Права проверяет политика маршрута; дедлайны потом не меняются (Р13)."""
    # Ввод проверяется до транзакции: неверный запрос не занимает соединение с БД.
    draft = NewContest.create(topic, description, submission_deadline, voting_deadline)

    async def work(session: AsyncSession) -> ContestDetails:
        now = clock.now()
        # Конкурс, у которого приём уже закрыт, начался бы сразу с голосования: это ошибка ввода.
        if draft.schedule.submission_deadline <= now:
            raise DeadlineInPastError("Срок закрытия приёма идей уже прошёл.")
        contest = await dao.insert_contest(
            session,
            topic=draft.topic,
            description=draft.description,
            schedule=draft.schedule,
            created_by=actor.user_id,
            created_at=now,
        )
        return ContestDetails.at(contest, actor, now)

    return await database.run_in_transaction(work)


async def list_contests(
    database: Database, clock: Clock, *, limit: int, offset: int
) -> ContestsPage:
    limit = max(1, min(limit, LIST_LIMIT_MAX))
    offset = max(0, offset)

    async def work(session: AsyncSession) -> ContestsPage:
        now = clock.now()
        contests = await dao.select_contests_page(session, limit=limit, offset=offset)
        total = await dao.count_contests(session)
        items = tuple((contest, contest.phase_at(now)) for contest in contests)
        return ContestsPage(items, total, now)

    return await database.run_in_transaction(work)


async def get_contest(
    database: Database, clock: Clock, actor: Actor, contest_id: ContestId
) -> ContestDetails:
    async def work(session: AsyncSession) -> ContestDetails:
        contest = await dao.select_contest(session, contest_id)
        if contest is None:
            raise ContestNotFoundError("Конкурс не найден.")
        return ContestDetails.at(contest, actor, clock.now())

    return await database.run_in_transaction(work)


async def lock_contest_for_share(session: AsyncSession, contest_id: ContestId) -> Contest:
    """Заблокировать конкурс `FOR SHARE` в транзакции записи другого модуля.

    Блокировка стоит первой в порядке contest → idea → vote (§7.2): финализация берёт
    `FOR UPDATE` и дожидается всех записей, начатых до дедлайна.
    """
    contest = await dao.select_contest(session, contest_id, lock_for_share=True)
    if contest is None:
        raise ContestNotFoundError("Конкурс не найден.")
    return contest


async def find_contest(session: AsyncSession, contest_id: ContestId) -> Contest:
    """Прочитать конкурс без блокировки (чтение списков)."""
    contest = await dao.select_contest(session, contest_id)
    if contest is None:
        raise ContestNotFoundError("Конкурс не найден.")
    return contest
