"""Сценарии идей: подача, правка, список (CLAUDE.md §7.2)."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import Actor, ContestId, IdeaId, ensure_actor_active
from app.contest import service as contest_service
from app.contest.model import ContestPhase, can_view_authors
from app.core.clock import Clock
from app.core.db import Database
from app.idea import dao
from app.idea.exception import (
    ContestFullError,
    IdeaLimitReachedError,
    IdeaNotFoundError,
    IdempotencyKeyReusedError,
    StaleIdeaVersionError,
)
from app.idea.model import (
    IDEAS_PER_AUTHOR_LIMIT,
    IDEAS_PER_CONTEST_LIMIT,
    Idea,
    IdeaContent,
    IdeaListing,
    ListedIdea,
    SubmittedIdea,
    can_view_idea,
    compute_request_hash,
    ensure_can_delete_idea,
    ensure_can_edit_idea,
    ensure_can_submit_idea,
)
from app.user import service as user_service


def _replay(stored: tuple[Idea, bytes | None], request_hash: bytes) -> SubmittedIdea:
    """Повтор принятого запроса: тот же ключ и то же тело — та же идея, иначе ошибка клиента."""
    idea, stored_hash = stored
    if stored_hash != request_hash:
        raise IdempotencyKeyReusedError("Этот ключ запроса уже использован с другими данными.")
    return SubmittedIdea(idea, created=False)


async def submit_idea(
    database: Database,
    clock: Clock,
    actor: Actor,
    contest_id: ContestId,
    *,
    client_request_id: UUID,
    title: str,
    description: str,
) -> SubmittedIdea:
    """Подать идею. Порядок шагов — §7.2; `now` читается после блокировки конкурса (Р4)."""
    # Ввод проверяется до транзакции: неверный запрос не занимает соединение с БД.
    content = IdeaContent.create(title, description)
    request_hash = compute_request_hash(contest_id, content)

    async def work(session: AsyncSession) -> SubmittedIdea:
        ensure_actor_active(actor)
        # Повтор ищем ДО проверки фазы: ответ на запрос, принятый перед дедлайном, но потерянный
        # по сети, при повторе после дедлайна должен вернуть принятую идею, а не 409 (П2).
        stored = await dao.select_idea_by_request(session, actor.user_id, client_request_id)
        if stored is not None:
            return _replay(stored, request_hash)
        contest = await contest_service.lock_contest_for_share(session, contest_id)
        now = clock.now()
        ensure_can_submit_idea(actor, contest.phase_at(now))
        # Лимиты мягкие: параллельные вставки под общей блокировкой могут превысить их на единицы,
        # корректность итога это не нарушает (§7.2).
        if await dao.count_author_ideas(session, contest_id, actor.user_id) >= (
            IDEAS_PER_AUTHOR_LIMIT
        ):
            raise IdeaLimitReachedError("Достигнут предел числа ваших идей в этом конкурсе.")
        if await dao.count_contest_ideas(session, contest_id) >= IDEAS_PER_CONTEST_LIMIT:
            raise ContestFullError("В конкурсе уже подано максимальное число идей.")
        idea = await dao.insert_idea_if_absent(
            session,
            contest_id=contest_id,
            author_id=actor.user_id,
            content=content,
            client_request_id=client_request_id,
            request_hash=request_hash,
            now=now,
        )
        if idea is not None:
            return SubmittedIdea(idea, created=True)
        # Параллельный запрос с тем же ключом закоммитился раньше: это повтор.
        stored = await dao.select_idea_by_request(session, actor.user_id, client_request_id)
        if stored is None:  # недостижимо: конфликт возможен только по этому ключу
            raise RuntimeError("идея не найдена после конфликта ключа повтора")
        return _replay(stored, request_hash)

    return await database.run_in_transaction(work)


async def edit_idea(
    database: Database,
    clock: Clock,
    actor: Actor,
    idea_id: IdeaId,
    *,
    title: str,
    description: str,
    version: int,
) -> Idea:
    """Править свою идею до закрытия приёма. Порядок блокировок contest → idea (Р6)."""
    content = IdeaContent.create(title, description)

    async def work(session: AsyncSession) -> Idea:
        ensure_actor_active(actor)
        # Конкурс идеи нужно знать до блокировок: сначала contest, потом idea.
        contest_id = await dao.select_idea_contest_id(session, idea_id)
        if contest_id is None:
            raise IdeaNotFoundError("Идея не найдена.")
        contest = await contest_service.lock_contest_for_share(session, contest_id)
        idea = await dao.select_idea(session, idea_id, lock_for_update=True)
        # 404 и для чужой идеи: ответ не раскрывает, что она существует (§7.2).
        if idea is None or not idea.is_authored_by(actor.user_id):
            raise IdeaNotFoundError("Идея не найдена.")
        # Те же поля — повтор уже применённой правки (ответ мог потеряться по сети): 200 в любой
        # фазе и при любой версии, проверка идёт до фазы и версии.
        if idea.content == content:
            return idea
        now = clock.now()
        ensure_can_edit_idea(actor, idea, contest.phase_at(now))
        if idea.version != version:
            raise StaleIdeaVersionError("Идею уже изменили в другой вкладке.")
        return await dao.update_idea_content(session, idea_id, content, now)

    return await database.run_in_transaction(work)


async def delete_idea(database: Database, clock: Clock, actor: Actor, idea_id: IdeaId) -> None:
    """Удалить свою идею вместе с голосами, пока конкурс не завершён (П11).

    Порядок блокировок тот же, что при правке и голосовании: contest → idea (Р6). Голос,
    ожидающий на блокировке идеи, после удаления получает 404, «сирот» не остаётся.
    """

    async def work(session: AsyncSession) -> None:
        ensure_actor_active(actor)
        contest_id = await dao.select_idea_contest_id(session, idea_id)
        if contest_id is None:
            raise IdeaNotFoundError("Идея не найдена.")
        contest = await contest_service.lock_contest_for_share(session, contest_id)
        idea = await dao.select_idea(session, idea_id, lock_for_update=True)
        if idea is None:
            raise IdeaNotFoundError("Идея не найдена.")
        ensure_can_delete_idea(actor, idea, contest.phase_at(clock.now()))
        await dao.delete_idea(session, idea_id)

    await database.run_in_transaction(work)


async def list_all_contest_ideas(session: AsyncSession, contest_id: ContestId) -> tuple[Idea, ...]:
    """Все идеи конкурса без проверки видимости: для подсчёта итогов (вызывает `result`).

    Кто вправе видеть итоги, решает вызывающий сервис по политике `result.model`.
    """
    return tuple(await dao.select_contest_ideas(session, contest_id))


async def find_idea_contest_id(session: AsyncSession, idea_id: IdeaId) -> ContestId | None:
    """Конкурс идеи без блокировок: вызывающий сначала блокирует конкурс (contest → idea)."""
    return await dao.select_idea_contest_id(session, idea_id)


async def lock_idea_for_share(session: AsyncSession, idea_id: IdeaId) -> Idea | None:
    """Идея под `FOR SHARE`: голоса не мешают друг другу, но удаление идеи дожидается их (Р6)."""
    return await dao.select_idea(session, idea_id, lock_for_share=True)


async def list_contest_ideas(
    session: AsyncSession, actor: Actor, contest_id: ContestId, now: datetime
) -> IdeaListing:
    """Идеи конкурса, которые вправе видеть `actor` в фазе на момент `now` (П3, П4).

    Вызывается из транзакции модуля `vote`, который добавляет к списку отметки голосов.
    Авторы подставляются только там, где политика их раскрывает (после финала).
    """
    ensure_actor_active(actor)
    contest = await contest_service.find_contest(session, contest_id)
    phase = contest.phase_at(now)
    if phase is ContestPhase.SUBMISSION:
        # Чужие идеи в приёме не читаются из БД вовсе: политика ниже — вторая преграда.
        ideas = await dao.select_contest_ideas(session, contest_id, author_id=actor.user_id)
    else:
        ideas = await dao.select_contest_ideas(
            session, contest_id, order_by_id=phase is ContestPhase.VOTING
        )
    visible = [idea for idea in ideas if can_view_idea(actor, idea, phase)]
    names = (
        await user_service.get_user_names(session, {idea.author_id for idea in visible})
        if can_view_authors(actor, phase)
        else {}
    )
    return IdeaListing(
        phase,
        tuple(
            ListedIdea(
                idea,
                is_mine=idea.is_authored_by(actor.user_id),
                author_name=names.get(idea.author_id),
            )
            for idea in visible
        ),
    )
