"""Запросы к таблице сессий. Транзакцией управляет service."""

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dao.tables import SessionRow
from app.auth.model import Session
from app.common.model import UserId


def _to_session(row: SessionRow) -> Session:
    return Session(
        id=row.id,
        user_id=UserId(row.user_id),
        created_at=row.created_at,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
    )


async def insert_session(
    session: AsyncSession,
    *,
    token_hash: bytes,
    user_id: UserId,
    created_at: datetime,
    expires_at: datetime,
) -> Session:
    row = SessionRow(
        token_hash=token_hash, user_id=user_id, created_at=created_at, expires_at=expires_at
    )
    session.add(row)
    await session.flush()
    return _to_session(row)


async def select_active_session(
    session: AsyncSession, token_hash: bytes, now: datetime
) -> Session | None:
    """Сессия действует, пока не отозвана и `now < expires_at` (на границе уже не действует)."""
    row = (
        await session.execute(
            select(SessionRow).where(
                SessionRow.token_hash == token_hash,
                SessionRow.revoked_at.is_(None),
                SessionRow.expires_at > now,
            )
        )
    ).scalar_one_or_none()
    return None if row is None else _to_session(row)


async def revoke_session(session: AsyncSession, token_hash: bytes, now: datetime) -> None:
    """Отозвать сессию; повторный отзыв не меняет время первого."""
    await session.execute(
        update(SessionRow)
        .where(SessionRow.token_hash == token_hash, SessionRow.revoked_at.is_(None))
        .values(revoked_at=now)
    )
