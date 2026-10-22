"""Запросы к таблице идей. Транзакцией управляет service."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId, IdeaId, UserId
from app.idea.dao.tables import IdeaRow
from app.idea.model import Idea, IdeaContent


def _to_idea(row: IdeaRow) -> Idea:
    return Idea(
        id=IdeaId(row.id),
        contest_id=ContestId(row.contest_id),
        author_id=UserId(row.author_id),
        content=IdeaContent(title=row.title, description=row.description),
        submitted_at=row.submitted_at,
        updated_at=row.updated_at,
        version=row.version,
    )


async def select_idea_by_request(
    session: AsyncSession, author_id: UserId, client_request_id: UUID
) -> tuple[Idea, bytes | None] | None:
    """Ранее принятая идея по ключу повтора вместе с отпечатком её запроса."""
    row = (
        await session.execute(
            select(IdeaRow).where(
                IdeaRow.author_id == author_id, IdeaRow.client_request_id == client_request_id
            )
        )
    ).scalar_one_or_none()
    return None if row is None else (_to_idea(row), row.request_hash)


async def insert_idea_if_absent(
    session: AsyncSession,
    *,
    contest_id: ContestId,
    author_id: UserId,
    content: IdeaContent,
    client_request_id: UUID,
    request_hash: bytes,
    now: datetime,
) -> Idea | None:
    """Вставить идею; `None`, если параллельный запрос с тем же ключом успел раньше."""
    statement = (
        pg_insert(IdeaRow)
        .values(
            contest_id=contest_id,
            author_id=author_id,
            title=content.title,
            description=content.description,
            submitted_at=now,
            updated_at=now,
            client_request_id=client_request_id,
            request_hash=request_hash,
        )
        .on_conflict_do_nothing(constraint="uq_ideas_author_request")
        .returning(IdeaRow)
    )
    row = (await session.execute(statement)).scalar_one_or_none()
    return None if row is None else _to_idea(row)


async def count_author_ideas(
    session: AsyncSession, contest_id: ContestId, author_id: UserId
) -> int:
    statement = (
        select(func.count())
        .select_from(IdeaRow)
        .where(IdeaRow.contest_id == contest_id, IdeaRow.author_id == author_id)
    )
    return int(await session.scalar(statement) or 0)


async def count_contest_ideas(session: AsyncSession, contest_id: ContestId) -> int:
    statement = select(func.count()).select_from(IdeaRow).where(IdeaRow.contest_id == contest_id)
    return int(await session.scalar(statement) or 0)


async def select_idea_contest_id(session: AsyncSession, idea_id: IdeaId) -> ContestId | None:
    """Конкурс идеи без блокировки: порядок блокировок contest → idea требует знать его заранее."""
    value = await session.scalar(select(IdeaRow.contest_id).where(IdeaRow.id == idea_id))
    return None if value is None else ContestId(value)


async def select_idea(
    session: AsyncSession, idea_id: IdeaId, *, lock_for_update: bool = False
) -> Idea | None:
    statement = select(IdeaRow).where(IdeaRow.id == idea_id)
    if lock_for_update:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    row = (await session.execute(statement)).scalar_one_or_none()
    return None if row is None else _to_idea(row)


async def update_idea_content(
    session: AsyncSession, idea_id: IdeaId, content: IdeaContent, now: datetime
) -> Idea:
    """Заменить текст и поднять версию; `submitted_at` не трогаем — по нему решается ничья (П10)."""
    statement = (
        update(IdeaRow)
        .where(IdeaRow.id == idea_id)
        .values(
            title=content.title,
            description=content.description,
            updated_at=now,
            version=IdeaRow.version + 1,
        )
        .returning(IdeaRow)
        .execution_options(populate_existing=True)
    )
    return _to_idea((await session.execute(statement)).scalar_one())


async def select_contest_ideas(
    session: AsyncSession,
    contest_id: ContestId,
    *,
    author_id: UserId | None = None,
    order_by_id: bool = False,
) -> list[Idea]:
    """Идеи конкурса. `order_by_id` — порядок голосования: по случайному UUID, без связи со
    временем подачи; иначе по времени подачи (порядок ничьей, П10)."""
    statement = select(IdeaRow).where(IdeaRow.contest_id == contest_id)
    if author_id is not None:
        statement = statement.where(IdeaRow.author_id == author_id)
    statement = statement.order_by(IdeaRow.id if order_by_id else IdeaRow.submitted_at, IdeaRow.id)
    return [_to_idea(row) for row in (await session.execute(statement)).scalars()]
