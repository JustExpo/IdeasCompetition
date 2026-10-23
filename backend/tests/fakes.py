"""Подставные реализации для тестов: управляемые часы."""

from datetime import datetime, timedelta
from enum import StrEnum

from app.common.model import require_aware
from app.core.db import Database
from app.notification.exception import EmailDeliveryError
from app.notification.model import OutgoingEmail


class FrozenClock:
    """Часы, которые стоят на месте, пока тест не сдвинет их (реализует `app.core.clock.Clock`)."""

    def __init__(self, start: datetime) -> None:
        require_aware(start, "start")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def set(self, moment: datetime) -> None:
        require_aware(moment, "moment")
        self._now = moment

    def advance(self, delta: timedelta) -> None:
        self._now += delta


class ReadyDatabase(Database):
    """`Database` для тестов HTTP-слоя без PostgreSQL: готовность всегда успешна, соединений нет."""

    async def check_ready(self) -> None:
        return None


class SendMode(StrEnum):
    """Что делает `FakeMailSender` с очередным письмом (CLAUDE.md §10.2)."""

    OK = "ok"
    REJECT_4XX = "reject_4xx"  # временный отказ SMTP
    REJECT_5XX = "reject_5xx"  # постоянный отказ SMTP
    TIMEOUT = "timeout"
    DISCONNECT = "disconnect"  # обрыв соединения
    GARBLED = "garbled"  # некорректный ответ сервера


class FakeMailSender:
    """Почтовый адаптер для тестов (реализует `EmailSender`): запоминает письма и играет сбои."""

    def __init__(self, mode: SendMode = SendMode.OK) -> None:
        self.mode = mode
        self.failing_recipients: set[str] = set()  # им всегда временный отказ, остальным — `mode`
        self.sent: list[OutgoingEmail] = []
        self.attempts = 0

    async def send(self, email: OutgoingEmail) -> None:
        self.attempts += 1
        if email.to_email in self.failing_recipients:
            raise EmailDeliveryError("SMTP: ответ 451.", permanent=False)
        failures = {
            SendMode.REJECT_4XX: ("SMTP: ответ 451.", False),
            SendMode.REJECT_5XX: ("SMTP: ответ 550.", True),
            SendMode.TIMEOUT: ("SMTP: таймаут.", False),
            SendMode.DISCONNECT: ("SMTP: SMTPServerDisconnected.", False),
            SendMode.GARBLED: ("SMTP: SMTPResponseException.", False),
        }
        if self.mode in failures:
            message, permanent = failures[self.mode]
            raise EmailDeliveryError(message, permanent=permanent)
        self.sent.append(email)

    def recipients(self) -> list[str]:
        return [email.to_email for email in self.sent]
