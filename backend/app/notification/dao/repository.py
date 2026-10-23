"""Запросы к outbox. Транзакцией управляет service."""

from datetime import datetime

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import UserId
from app.notification.dao.tables import OutboxEmailRow
from app.notification.model import EmailKind, EmailStatus, OutboxEmail


def _to_email(row: OutboxEmailRow) -> OutboxEmail:
    return OutboxEmail(
        id=row.id,
        dedup_key=row.dedup_key,
        kind=EmailKind(row.kind),
        user_id=None if row.user_id is None else UserId(row.user_id),
        to_email=row.to_email,
        subject=row.subject,
        body=row.body,
        status=EmailStatus(row.status),
        attempts=row.attempts,
        next_attempt_at=row.next_attempt_at,
        created_at=row.created_at,
        not_after=row.not_after,
        sent_at=row.sent_at,
        last_error=row.last_error,
    )


async def insert_email_if_absent(
    session: AsyncSession,
    *,
    dedup_key: str,
    kind: EmailKind,
    user_id: UserId | None,
    to_email: str,
    subject: str,
    body: str,
    now: datetime,
    not_after: datetime | None,
) -> bool:
    """Поставить письмо в очередь; `False`, если письмо с таким `dedup_key` уже есть."""
    statement = (
        pg_insert(OutboxEmailRow)
        .values(
            dedup_key=dedup_key,
            kind=kind.value,
            user_id=user_id,
            to_email=to_email,
            subject=subject,
            body=body,
            status=EmailStatus.PENDING.value,
            attempts=0,
            next_attempt_at=now,
            not_after=not_after,
            created_at=now,
        )
        .on_conflict_do_nothing(index_elements=["dedup_key"])
        .returning(OutboxEmailRow.id)
    )
    return (await session.execute(statement)).first() is not None


async def lock_due_emails(session: AsyncSession, now: datetime, limit: int) -> list[OutboxEmail]:
    """Письма, которые пора отправить: ждущие или с истёкшей арендой (проход упал на полпути).

    `SKIP LOCKED` — параллельный проход не ждёт и не берёт те же строки.
    """
    statement = (
        select(OutboxEmailRow)
        .where(
            or_(
                and_(
                    OutboxEmailRow.status == EmailStatus.PENDING.value,
                    OutboxEmailRow.next_attempt_at <= now,
                ),
                and_(
                    OutboxEmailRow.status == EmailStatus.SENDING.value,
                    OutboxEmailRow.lease_until < now,
                ),
            )
        )
        .order_by(OutboxEmailRow.next_attempt_at, OutboxEmailRow.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .execution_options(populate_existing=True)
    )
    return [_to_email(row) for row in (await session.execute(statement)).scalars()]


async def mark_sending(
    session: AsyncSession, email_id: int, *, lease_until: datetime, attempts: int
) -> None:
    await session.execute(
        update(OutboxEmailRow)
        .where(OutboxEmailRow.id == email_id)
        .values(status=EmailStatus.SENDING.value, lease_until=lease_until, attempts=attempts)
    )


async def mark_finished(
    session: AsyncSession,
    email_id: int,
    *,
    status: EmailStatus,
    now: datetime,
    error: str | None,
) -> None:
    """Перевести письмо в конечный статус (`sent`, `failed`, `expired`)."""
    await session.execute(
        update(OutboxEmailRow)
        .where(OutboxEmailRow.id == email_id, OutboxEmailRow.status == EmailStatus.SENDING.value)
        .values(
            status=status.value,
            lease_until=None,
            sent_at=now if status is EmailStatus.SENT else None,
            last_error=error,
        )
    )


async def mark_retry(
    session: AsyncSession, email_id: int, *, next_attempt_at: datetime, error: str
) -> None:
    await session.execute(
        update(OutboxEmailRow)
        .where(OutboxEmailRow.id == email_id, OutboxEmailRow.status == EmailStatus.SENDING.value)
        .values(
            status=EmailStatus.PENDING.value,
            lease_until=None,
            next_attempt_at=next_attempt_at,
            last_error=error,
        )
    )


async def select_email_by_dedup_key(session: AsyncSession, dedup_key: str) -> OutboxEmail | None:
    row = (
        await session.execute(
            select(OutboxEmailRow)
            .where(OutboxEmailRow.dedup_key == dedup_key)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return None if row is None else _to_email(row)
