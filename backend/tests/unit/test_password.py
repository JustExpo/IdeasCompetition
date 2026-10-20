"""Правила пароля и сервис хэширования Argon2id (CLAUDE.md §9.1)."""

import asyncio
import contextlib
import threading

import pytest

from app.auth.service import PasswordService
from app.auth.service.passwords import (
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
)
from app.common.model import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    is_password_length_valid,
    normalize_password,
)


@pytest.mark.parametrize(
    ("length", "valid"),
    [
        (PASSWORD_MIN_LENGTH - 1, False),
        (PASSWORD_MIN_LENGTH, True),
        (PASSWORD_MAX_LENGTH, True),
        (PASSWORD_MAX_LENGTH + 1, False),
    ],
)
def test_password_length_boundaries(length: int, valid: bool) -> None:
    assert is_password_length_valid("p" * length) is valid


def test_length_is_counted_after_nfkc_normalization() -> None:
    # «ﬁ» (лигатура, 1 символ) после NFKC превращается в «fi» (2 символа)
    nine_with_ligature = "ﬁ" + "a" * 8
    assert len(nine_with_ligature) == 9
    assert len(normalize_password(nine_with_ligature)) == 10
    assert is_password_length_valid(nine_with_ligature)


def test_same_password_in_different_unicode_forms_normalizes_equal() -> None:
    assert normalize_password("é-password") == normalize_password("é-password")


def test_argon2_parameters_follow_owasp() -> None:
    assert (ARGON2_MEMORY_COST_KIB, ARGON2_TIME_COST, ARGON2_PARALLELISM) == (19 * 1024, 2, 1)


async def test_hash_verifies_only_the_right_password() -> None:
    service = PasswordService()
    password_hash = await service.hash_password("correct-horse-battery")
    assert password_hash.startswith("$argon2id$")
    assert await service.verify_password(password_hash, "correct-horse-battery")
    assert not await service.verify_password(password_hash, "correct-horse-batterz")
    assert not service.needs_rehash(password_hash)


async def test_garbage_hash_does_not_verify_or_raise() -> None:
    assert not await PasswordService().verify_password("not-a-hash", "whatever-password")


async def test_hash_with_weaker_parameters_needs_rehash() -> None:
    from argon2 import PasswordHasher

    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("some-password-10")
    assert PasswordService().needs_rehash(weak)


async def test_unknown_account_check_runs_without_error() -> None:
    await PasswordService().verify_unknown_account("some-password-10")


class BlockingHasher:
    """Подмена Argon2: считает одновременные вызовы и держит их, пока тест не отпустит."""

    def __init__(self, loop: asyncio.AbstractEventLoop, limit_reached: asyncio.Event) -> None:
        self._loop = loop
        self._limit_reached = limit_reached
        self._lock = threading.Lock()
        self.release = threading.Event()
        self.in_flight = 0
        self.max_in_flight = 0

    def hash(self, password: str) -> str:
        return password

    def verify(self, hash: str, password: str) -> bool:
        with self._lock:
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            if self.in_flight == 4:
                self._loop.call_soon_threadsafe(self._limit_reached.set)
        self.release.wait(timeout=10)
        with self._lock:
            self.in_flight -= 1
        return True

    def check_needs_rehash(self, hash: str) -> bool:
        return False


async def test_ten_concurrent_checks_never_exceed_the_semaphore() -> None:
    limit_reached = asyncio.Event()
    hasher = BlockingHasher(asyncio.get_running_loop(), limit_reached)
    service = PasswordService(concurrency=4, hasher=hasher)
    checks = asyncio.gather(*(service.verify_password("h", "p") for _ in range(10)))

    await asyncio.wait_for(limit_reached.wait(), timeout=5)
    # Дать остальным шесть задачам возможность (ошибочно) стартовать, пока слоты заняты.
    with contextlib.suppress(TimeoutError):
        async with asyncio.timeout(0.3):
            await asyncio.Event().wait()
    assert hasher.in_flight == 4

    hasher.release.set()
    assert await asyncio.wait_for(checks, timeout=10) == [True] * 10
    assert hasher.max_in_flight == 4
