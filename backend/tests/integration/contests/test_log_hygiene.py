"""Логи без паролей, токенов, cookie, текстов идей и связки автор ↔ идея (CLAUDE.md §13, §6.5)."""

import io
import logging
from collections.abc import Awaitable, Callable, Iterator

import httpx
import pytest

from app.core.db import Database
from app.core.logging import clear_log_context, configure_logging, shutdown_logging
from app.result.service import finalize_due_contests
from tests.fakes import FrozenClock
from tests.integration.contests.conftest import VOTING_DEADLINE, Person, call
from tests.integration.contests.mailbox import PUBLIC_URL, run_to_voting, vote_for

pytestmark = pytest.mark.commits

PASSWORD_MARKER = "Pa55-marker-never-in-logs"  # gitleaks:allow — фиктивное значение
TITLE_MARKER = "Заголовок-маркер-4471"
DESCRIPTION_MARKER = "Описание-маркер-9032"


@pytest.fixture
def log_stream(monkeypatch: pytest.MonkeyPatch) -> Iterator[io.StringIO]:
    buffer = io.StringIO()
    configure_logging(level="DEBUG", fmt="json", stream=buffer)
    # Тестовый клиент httpx пишет полный URL запроса (с id идеи) в тот же корневой logger;
    # это не лог приложения, поэтому проверяется только он.
    monkeypatch.setattr(logging.getLogger("httpx"), "level", logging.WARNING)
    yield buffer
    clear_log_context()
    shutdown_logging()


def assert_log_is_clean(log: str, forbidden: dict[str, str]) -> None:
    """Падает, если в логе есть любое из запрещённых значений; `forbidden`: описание → значение."""
    leaked = [label for label, value in forbidden.items() if value in log]
    assert not leaked, f"в логе найдено: {', '.join(leaked)}"


def test_checker_notices_an_intentional_email_leak() -> None:
    # Без этой проверки «чистый лог» мог бы означать просто слепой детектор.
    with pytest.raises(AssertionError, match="e-mail"):
        assert_log_is_clean('{"event": "oops anna@example.com"}', {"e-mail": "anna@example.com"})


async def test_full_flow_leaves_no_secrets_or_authorship_in_logs(
    client: httpx.AsyncClient,
    database: Database,
    clock: FrozenClock,
    log_stream: io.StringIO,
    new_contest: Callable[..., Awaitable[int]],
    new_idea: Callable[..., Awaitable[httpx.Response]],
    anna: Person,
    boris: Person,
    organizer: Person,
) -> None:
    contest_id = await new_contest()
    first = await new_idea(
        anna, contest_id, title=f"{TITLE_MARKER} A", description=f"{DESCRIPTION_MARKER} A"
    )
    second = await new_idea(
        boris, contest_id, title=f"{TITLE_MARKER} B", description=f"{DESCRIPTION_MARKER} B"
    )
    idea_ids = [str(first.json()["id"]), str(second.json()["id"])]
    # Нарушения тоже пишутся в лог: вход с неверным паролем, чужая идея, голос за свою.
    bad_login = await call(
        client,
        None,
        "POST",
        "/api/auth/login",
        json={"email": "anna@example.com", "password": PASSWORD_MARKER},
    )
    assert bad_login.status_code == 401
    assert (await call(client, boris, "PATCH", f"/api/ideas/{idea_ids[0]}", json={})).is_error

    run = await run_to_voting(client, clock, new_contest, new_idea, [(anna, "Идея")])
    await vote_for(client, boris, run.ideas["Идея"])
    own = await call(client, anna, "PUT", f"/api/ideas/{run.ideas['Идея']}/vote")
    assert own.status_code == 403
    clock.set(VOTING_DEADLINE)
    await finalize_due_contests(database, clock, public_base_url=PUBLIC_URL)
    await call(client, anna, "POST", "/api/auth/logout")

    log = log_stream.getvalue()
    assert log, "лог не должен быть пустым: иначе проверка ничего не проверяет"
    forbidden = {
        "пароль": PASSWORD_MARKER,
        "заголовок идеи": TITLE_MARKER,
        "описание идеи": DESCRIPTION_MARKER,
        **{f"токен сессии {person.name}": person.cookie for person in (anna, boris, organizer)},
        **{
            f"e-mail {person.name}": f"{person.name.lower()}@example.com"
            for person in (anna, boris, organizer)
        },
        **{f"идентификатор идеи {i}": idea_id for i, idea_id in enumerate(idea_ids)},
        "идентификатор идеи голосования": run.ideas["Идея"],
    }
    assert_log_is_clean(log, forbidden)
