"""Планировщик: тик под блокировкой, изоляция ошибок задач, цикл (CLAUDE.md §8.4; IC-020)."""

import asyncio

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.db import Database
from app.core.scheduler import TICK_LOCK_KEY, ScheduledJob, Scheduler
from app.main import create_app
from app.notification.model import OutgoingEmail
from app.result.handler import run_finalization
from tests.fakes import FakeMailSender, FrozenClock
from tests.integration.contests.conftest import VOTING_DEADLINE, Person
from tests.integration.contests.mailbox import (
    PUBLIC_URL,
    NewContest,
    NewIdea,
    outbox_rows,
    run_to_voting,
    vote_for,
)

pytestmark = pytest.mark.commits


class Recorder:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def job(self, name: str, *, fail: bool = False) -> ScheduledJob:
        async def run() -> None:
            self.calls.append(name)
            if fail:
                raise RuntimeError("сбой задачи")

        return ScheduledJob(name, run)


async def test_failed_job_does_not_stop_other_jobs(database: Database) -> None:
    recorder = Recorder()
    scheduler = Scheduler(
        database,
        [recorder.job("first", fail=True), recorder.job("second")],
        interval_s=15,
    )

    assert await scheduler.run_tick() is True

    assert recorder.calls == ["first", "second"]


async def test_tick_is_skipped_while_another_process_holds_the_lock(database: Database) -> None:
    recorder = Recorder()
    scheduler = Scheduler(database, [recorder.job("job")], interval_s=15)
    locked = asyncio.Event()
    release = asyncio.Event()

    async def hold(session: AsyncSession) -> None:
        await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": TICK_LOCK_KEY})
        locked.set()
        await release.wait()

    holder = asyncio.create_task(database.run_in_transaction(hold))
    await locked.wait()

    skipped = await scheduler.run_tick()
    release.set()
    await holder

    assert skipped is False
    assert recorder.calls == []
    assert await scheduler.run_tick() is True  # блокировка снята вместе с транзакцией


async def test_two_ticks_finalize_once(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
) -> None:
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)

    async def finalize() -> None:
        await run_finalization(database, clock, public_base_url=PUBLIC_URL)

    scheduler = Scheduler(database, [ScheduledJob("finalization", finalize)], interval_s=15)
    await scheduler.run_tick()
    await scheduler.run_tick()

    assert len(await outbox_rows(database)) == 2


async def test_loop_runs_first_tick_at_start_and_stops_between_ticks(database: Database) -> None:
    ticked = asyncio.Event()

    async def run() -> None:
        ticked.set()

    scheduler = Scheduler(database, [ScheduledJob("job", run)], interval_s=3600)
    scheduler.start()
    await asyncio.wait_for(ticked.wait(), timeout=10)

    await asyncio.wait_for(scheduler.stop(), timeout=10)


class SignalingSender(FakeMailSender):
    def __init__(self) -> None:
        super().__init__()
        self.delivered = asyncio.Event()

    async def send(self, email: OutgoingEmail) -> None:
        await super().send(email)
        self.delivered.set()


async def test_app_lifespan_runs_finalization_and_delivery_at_start(
    settings: Settings,
    database: Database,
    clock: FrozenClock,
    client: httpx.AsyncClient,
    new_contest: NewContest,
    new_idea: NewIdea,
    anna: Person,
    boris: Person,
) -> None:
    """Первый тик идёт сразу при старте: итог зафиксирован и письмо отправлено без ожидания."""
    contest = await run_to_voting(
        client, clock, new_contest, new_idea, [(anna, "Идея Анны"), (boris, "Идея Бориса")]
    )
    await vote_for(client, boris, contest.ideas["Идея Анны"])
    clock.set(VOTING_DEADLINE)
    sender = SignalingSender()
    app = create_app(settings, database, clock=clock, email_sender=sender)

    async with app.router.lifespan_context(app):
        await asyncio.wait_for(sender.delivered.wait(), timeout=10)

    assert set(sender.recipients()) <= {"anna@example.com", "boris@example.com"}
    assert sender.sent


async def test_stop_cancels_a_tick_that_outlives_the_grace_period(database: Database) -> None:
    started = asyncio.Event()
    never = asyncio.Event()

    async def run() -> None:
        if started.is_set():  # повторный тик после остановки не должен зависать
            return
        started.set()
        await never.wait()

    scheduler = Scheduler(database, [ScheduledJob("stuck", run)], interval_s=3600)
    scheduler.start()
    await asyncio.wait_for(started.wait(), timeout=10)

    await asyncio.wait_for(scheduler.stop(grace_s=0.05), timeout=10)

    assert await scheduler.run_tick() is True  # блокировка тика не осталась занятой
