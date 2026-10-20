"""Хэширование паролей Argon2id (CLAUDE.md §9.1).

Хэширование и проверка — CPU и память (19 МиБ на вызов), поэтому идут в пуле потоков под
семафором: при лимите памяти контейнера 512 МиБ пачка одновременных входов не должна
съесть всю память (OOM) и не должна блокировать event loop.
"""

import asyncio
import secrets
from typing import Final, Protocol

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MAX_CONCURRENT_HASHES: Final = 4
# Параметры OWASP для Argon2id: m=19 МиБ, t=2, p=1.
ARGON2_MEMORY_COST_KIB: Final = 19 * 1024
ARGON2_TIME_COST: Final = 2
ARGON2_PARALLELISM: Final = 1


class Hasher(Protocol):
    """Часть интерфейса `argon2.PasswordHasher`, которая нужна сервису (подменяется в тестах)."""

    def hash(self, password: str) -> str: ...

    def verify(self, hash: str, password: str) -> bool: ...

    def check_needs_rehash(self, hash: str) -> bool: ...


class PasswordService:
    def __init__(
        self, *, concurrency: int = MAX_CONCURRENT_HASHES, hasher: Hasher | None = None
    ) -> None:
        self._hasher: Hasher = hasher or PasswordHasher(
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST_KIB,
            parallelism=ARGON2_PARALLELISM,
        )
        self._slots = asyncio.Semaphore(concurrency)
        self._dummy_hash: str | None = None

    async def hash_password(self, password: str) -> str:
        """`password` уже нормализован (NFKC) вызывающим."""
        async with self._slots:
            return await asyncio.to_thread(self._hasher.hash, password)

    async def verify_password(self, password_hash: str, password: str) -> bool:
        async with self._slots:
            return await asyncio.to_thread(self._verify, password_hash, password)

    async def verify_unknown_account(self, password: str) -> None:
        """Потратить столько же времени, сколько проверка настоящего хэша.

        Иначе по скорости ответа можно отличить неизвестный e-mail от неверного пароля.
        """
        if self._dummy_hash is None:
            self._dummy_hash = await self.hash_password(secrets.token_urlsafe(16))
        await self.verify_password(self._dummy_hash, password)

    def needs_rehash(self, password_hash: str) -> bool:
        return self._hasher.check_needs_rehash(password_hash)

    def _verify(self, password_hash: str, password: str) -> bool:
        try:
            return self._hasher.verify(password_hash, password)
        except (VerificationError, InvalidHashError):
            return False
