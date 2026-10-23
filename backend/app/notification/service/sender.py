"""Отправка письма по SMTP. Единственное место, где модуль ходит в сеть (CLAUDE.md §10.2)."""

from email.message import EmailMessage
from typing import Protocol

import aiosmtplib

from app.notification.exception import EmailDeliveryError
from app.notification.model import OutgoingEmail

SMTP_TIMEOUT_S = 10.0
_PERMANENT_REPLY_MIN = 500


class EmailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> None:
        """Отправить письмо или бросить `EmailDeliveryError` (постоянная или временная)."""
        ...


def build_message(email: OutgoingEmail, mail_from: str) -> EmailMessage:
    """Письмо с заголовками через `EmailMessage`: перевод строки в теме или адресе отклоняется
    самим классом, поэтому инъекция заголовков невозможна."""
    message = EmailMessage()
    try:
        message["From"] = mail_from
        message["To"] = email.to_email
        message["Subject"] = email.subject
        message["Message-ID"] = email.message_id
        message.set_content(email.body)
    except ValueError as error:
        raise EmailDeliveryError(
            "Недопустимые символы в заголовках письма.", permanent=True
        ) from error
    return message


class SmtpEmailSender:
    """Отправка через aiosmtplib без TLS и авторизации: так работает Mailpit в локальном стеке."""

    def __init__(self, host: str, port: int, mail_from: str) -> None:
        self._host = host
        self._port = port
        self._mail_from = mail_from

    async def send(self, email: OutgoingEmail) -> None:
        message = build_message(email, self._mail_from)
        try:
            await aiosmtplib.send(
                message, hostname=self._host, port=self._port, timeout=SMTP_TIMEOUT_S
            )
        except aiosmtplib.SMTPRecipientsRefused as error:
            raise EmailDeliveryError("SMTP: адресат отвергнут.", permanent=True) from error
        except aiosmtplib.SMTPResponseException as error:
            permanent = error.code >= _PERMANENT_REPLY_MIN
            raise EmailDeliveryError(f"SMTP: ответ {error.code}.", permanent=permanent) from error
        except TimeoutError as error:
            raise EmailDeliveryError("SMTP: таймаут.", permanent=False) from error
        except (aiosmtplib.SMTPException, OSError) as error:
            # Обрыв, отказ в соединении, некорректный ответ: сервер может оправиться.
            raise EmailDeliveryError(f"SMTP: {type(error).__name__}.", permanent=False) from error
