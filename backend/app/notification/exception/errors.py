"""Ошибки доставки письма."""

from app.common.exception import AppError


class EmailDeliveryError(AppError):
    """Почтовый сервер не принял письмо.

    `permanent=True` — повтор бесполезен (5xx, адрес отвергнут); иначе письмо вернётся в очередь.
    Текст ошибки не содержит адресов: он попадает в `last_error` и в лог.
    """

    code = "email_delivery_failed"
    status = 502

    def __init__(self, message: str, *, permanent: bool) -> None:
        super().__init__(message)
        self.permanent = permanent
