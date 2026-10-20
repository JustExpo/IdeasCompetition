"""JSON-логи (CLAUDE.md §13): поля контекста через contextvars, ПДн не попадают в вывод.

Маскирование стоит в цепочке structlog, до форматтера: так оно действует и для логов
приложения, и для стандартного `logging` (uvicorn, SQLAlchemy), и для текста исключений.
"""

import logging
import re
import sys
from collections.abc import Mapping
from typing import Final, Literal, TextIO

import structlog
from structlog.typing import EventDict, Processor

REDACTED: Final = "[REDACTED]"
# Поля, значения которых не пишутся в лог ни при каких условиях: секреты и тексты пользователей.
SENSITIVE_KEYS: Final = frozenset(
    {
        "password",
        "passwd",
        "token",
        "secret",
        "cookie",
        "set_cookie",
        "set-cookie",
        "authorization",
        "sid",
        "body",
        "title",
        "description",
    }
)
_EMAIL_PATTERN: Final = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_HANDLER_MARK: Final = "_ideas_log_handler"


def mask_email(address: str) -> str:
    """alice@example.com -> a***@example.com: домен компании виден, адресат — нет."""
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def mask_emails_in_text(text: str) -> str:
    return _EMAIL_PATTERN.sub(lambda match: mask_email(match.group(0)), text)


def _scrub(value: object, key: str | None = None) -> object:
    if key is not None and key.lower() in SENSITIVE_KEYS:
        return REDACTED
    if isinstance(value, str):
        return mask_emails_in_text(value)
    if isinstance(value, Mapping):
        return {str(k): _scrub(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [_scrub(item) for item in value]
    return value


def scrub_sensitive(_logger: object, _method: str, event_dict: EventDict) -> EventDict:
    """Процессор structlog: прячет секреты по имени поля и e-mail по виду значения."""
    return {key: _scrub(value, key) for key, value in event_dict.items()}


def _shared_processors() -> list[Processor]:
    return [
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="ts"),
        structlog.processors.format_exc_info,
        scrub_sensitive,
    ]


def configure_logging(
    *,
    level: str = "INFO",
    fmt: Literal["json", "console"] = "json",
    stream: TextIO | None = None,
) -> None:
    """Настраивает structlog и корневой logger; повторный вызов заменяет прежний обработчик."""
    shared = _shared_processors()
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.contextvars.merge_contextvars,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    renderer: Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if fmt == "json"
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    setattr(handler, _HANDLER_MARK, True)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=[structlog.contextvars.merge_contextvars, *shared],
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    shutdown_logging()
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(level)


def shutdown_logging() -> None:
    """Снимает обработчик, поставленный `configure_logging`, чужие обработчики не трогает."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_MARK, False):
            root.removeHandler(handler)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger


def bind_log_context(**values: str | int | None) -> None:
    """Добавляет поля (request_id, user_id, contest_id...) во все записи текущей задачи."""
    structlog.contextvars.bind_contextvars(**values)


def clear_log_context() -> None:
    structlog.contextvars.clear_contextvars()
