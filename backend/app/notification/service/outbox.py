"""Постановка письма в очередь: вызывается из транзакции события (Р9)."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.model import ContestId, UserId
from app.notification import dao
from app.notification.model import EmailKind


def build_dedup_key(kind: EmailKind, contest_id: ContestId, user_id: UserId) -> str:
    """Один адресат получает письмо одного вида по одному конкурсу не больше раза."""
    return f"{kind.value}:{int(contest_id)}:{int(user_id)}"


async def enqueue_email(
    session: AsyncSession,
    *,
    kind: EmailKind,
    contest_id: ContestId,
    user_id: UserId,
    to_email: str,
    subject: str,
    body: str,
    now: datetime,
    not_after: datetime | None = None,
) -> bool:
    """Создать письмо в той же транзакции, что и событие. `False` — такое письмо уже есть.

    `not_after` — момент, после которого письмо бессмысленно (напоминание после дедлайна).
    """
    return await dao.insert_email_if_absent(
        session,
        dedup_key=build_dedup_key(kind, contest_id, user_id),
        kind=kind,
        user_id=user_id,
        to_email=to_email,
        subject=subject,
        body=body,
        now=now,
        not_after=not_after,
    )
