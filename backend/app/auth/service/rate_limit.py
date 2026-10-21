"""Ограничение частоты попыток входа и регистрации (CLAUDE.md §9.3).

Счётчики хранятся в памяти процесса (Р8: один процесс) и сбрасываются при перезапуске:
известное ограничение локального объёма.
"""

from typing import Final

from limits import RateLimitItem, parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter

from app.auth.exception import TooManyLoginAttemptsError, TooManyRegistrationsError

LOGIN_LIMIT: Final[RateLimitItem] = parse("5/15 minutes")  # неудачные входы на (e-mail, IP)
REGISTRATION_LIMIT: Final[RateLimitItem] = parse("5/hour")  # попытки регистрации на IP


class AttemptLimiter:
    """Лимиты по e-mail и IP. Адрес клиента — `request.client`, заголовкам прокси не верим."""

    def __init__(self, *, per_ip_enabled: bool = True) -> None:
        self._per_ip_enabled = per_ip_enabled
        self._window = MovingWindowRateLimiter(MemoryStorage())

    def _login_key(self, email: str, client_ip: str) -> tuple[str, ...]:
        # Без per-IP лимита (только e2e) вход всё равно ограничен по адресу почты.
        parts = ("login", email.strip().lower())
        return (*parts, client_ip) if self._per_ip_enabled else parts

    def ensure_login_allowed(self, email: str, client_ip: str) -> None:
        if not self._window.test(LOGIN_LIMIT, *self._login_key(email, client_ip)):
            raise TooManyLoginAttemptsError("Слишком много попыток входа. Повторите позже.")

    def record_failed_login(self, email: str, client_ip: str) -> None:
        # Считаем только неудачи: удачный вход подбором не получить, а честный пользователь
        # с несколькими вкладками не упирается в лимит.
        self._window.hit(LOGIN_LIMIT, *self._login_key(email, client_ip))

    def ensure_registration_allowed(self, client_ip: str) -> None:
        if self._per_ip_enabled and not self._window.hit(REGISTRATION_LIMIT, "register", client_ip):
            raise TooManyRegistrationsError("Слишком много попыток регистрации. Повторите позже.")
