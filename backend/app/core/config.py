"""Настройки приложения из окружения (CLAUDE.md §11.2).

Ошибки собираются целиком и печатаются без значений: пароль, строка подключения и адреса
не должны попасть в лог запуска (§9.4, §13).
"""

import sys
from typing import Annotated, Final, Literal
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import EmailStr, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

AppEnv = Literal["dev", "e2e", "prod"]

# Совпадает с `.env.example`: в prod такой пароль считается незаменённой заглушкой.
EXAMPLE_ORGANIZER_PASSWORD: Final = "dev-only-change-me-organizer"  # noqa: S105 — заглушка, не секрет
PASSWORD_MIN_LENGTH: Final = 10
PASSWORD_MAX_LENGTH: Final = 128
PROD_ORGANIZER_PASSWORD_MIN_LENGTH: Final = 16
DEV_FRONTEND_ORIGIN: Final = "http://localhost:5173"
CONFIG_EXIT_CODE: Final = 2


class Settings(BaseSettings):
    """Все настройки; имя переменной окружения совпадает с именем поля (без регистра)."""

    # Пустая переменная — не то же самое, что отсутствующая:
    # "" не подменяется значением по умолчанию, а считается неверным значением.
    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=False)

    app_env: AppEnv
    database_url: SecretStr
    organizer_email: EmailStr
    organizer_password: SecretStr
    organizer_name: str = Field(min_length=1, max_length=200)
    allowed_email_domains: Annotated[tuple[str, ...], NoDecode]
    public_base_url: str = Field(min_length=1)
    smtp_host: str = Field(min_length=1)
    smtp_port: int = Field(ge=1, le=65535)
    mail_from: EmailStr
    display_tz: str = "Europe/Moscow"
    scheduler_interval_s: int = Field(default=15, ge=5, le=300)
    web_concurrency: int = 1
    run_scheduler: bool = True
    hold_singleton_lock: bool = True
    test_clock_enabled: bool = False
    rate_limit_per_ip_enabled: bool = True
    seed_demo: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"

    @field_validator("allowed_email_domains", mode="before")
    @classmethod
    def split_email_domains(cls, value: object) -> object:
        if isinstance(value, str):
            return tuple(part.strip().lower() for part in value.split(",") if part.strip())
        return value

    @field_validator("allowed_email_domains")
    @classmethod
    def ensure_email_domains_valid(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("нужен хотя бы один домен")
        for domain in value:
            labels = domain.split(".")
            if len(labels) < 2 or not all(label.replace("-", "").isalnum() for label in labels):
                raise ValueError("домен должен быть вида example.com")
        return value

    @field_validator("display_tz")
    @classmethod
    def ensure_display_tz_known(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError, OSError):
            raise ValueError("неизвестный IANA-пояс, например Europe/Moscow") from None
        return value

    @model_validator(mode="after")
    def ensure_rules_for_environment(self) -> "Settings":
        problems = collect_environment_problems(self)
        if problems:
            raise ValueError("\n".join(problems))
        return self

    @property
    def public_origin(self) -> str:
        parts = urlsplit(self.public_base_url)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def allowed_origins(self) -> tuple[str, ...]:
        """Источники, которым разрешены небезопасные методы и WebSocket (CLAUDE.md §9.3)."""
        if self.app_env == "dev":
            return (self.public_origin, DEV_FRONTEND_ORIGIN)
        return (self.public_origin,)


def collect_environment_problems(settings: Settings) -> list[str]:
    """Правила, зависящие от среды и от нескольких полей сразу; текст без значений."""
    problems: list[str] = []
    env = settings.app_env

    try:
        db = urlsplit(settings.database_url.get_secret_value())
        db_name = db.path.lstrip("/")
        if db.scheme != "postgresql+asyncpg" or not db.hostname or not db_name:
            problems.append("DATABASE_URL: ожидается postgresql+asyncpg://пользователь@хост/база")
        elif env == "e2e" and not db_name.endswith("_e2e"):
            problems.append("DATABASE_URL: при APP_ENV=e2e имя базы должно оканчиваться на _e2e")
    except ValueError:
        problems.append("DATABASE_URL: адрес не разобран")

    password = settings.organizer_password.get_secret_value()
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        problems.append(
            f"ORGANIZER_PASSWORD: длина от {PASSWORD_MIN_LENGTH} до {PASSWORD_MAX_LENGTH} символов"
        )
    if env == "prod":
        if len(password) < PROD_ORGANIZER_PASSWORD_MIN_LENGTH:
            problems.append(
                "ORGANIZER_PASSWORD: в prod не короче "
                f"{PROD_ORGANIZER_PASSWORD_MIN_LENGTH} символов"
            )
        if password == EXAMPLE_ORGANIZER_PASSWORD:
            problems.append("ORGANIZER_PASSWORD: в prod нельзя оставлять пароль из .env.example")

    url = urlsplit(settings.public_base_url)
    if url.scheme not in {"http", "https"} or not url.netloc:
        problems.append("PUBLIC_BASE_URL: ожидается адрес вида http(s)://хост[:порт]")
    elif env == "prod" and url.scheme != "https":
        problems.append("PUBLIC_BASE_URL: в prod нужен https")

    if settings.web_concurrency != 1:
        problems.append(
            "WEB_CONCURRENCY: допустимо только 1 (шина событий и планировщик в процессе)"
        )
    if settings.test_clock_enabled and env != "e2e":
        problems.append("TEST_CLOCK_ENABLED: включается только при APP_ENV=e2e")
    if not settings.rate_limit_per_ip_enabled and env != "e2e":
        problems.append("RATE_LIMIT_PER_IP_ENABLED: отключается только при APP_ENV=e2e")
    if settings.seed_demo and env == "prod":
        problems.append("SEED_DEMO: включается только при APP_ENV=dev или e2e")
    return problems


def load_settings() -> Settings:
    """Читает окружение; при ошибке печатает все проблемные поля и завершает процесс кодом 2."""
    try:
        return Settings()
    except ValidationError as error:
        sys.stderr.write(format_config_error(error))
        raise SystemExit(CONFIG_EXIT_CODE) from None


def format_config_error(error: ValidationError) -> str:
    lines = ["Ошибка конфигурации (значения не выводятся):"]
    for item in error.errors(include_input=False, include_url=False, include_context=False):
        field = ".".join(str(part) for part in item["loc"]).upper()
        message = item["msg"].removeprefix("Value error, ")
        if item["type"] == "missing":
            lines.append(f"  - {field}: переменная не задана")
        elif field:
            lines.append(f"  - {field}: {message}")
        else:
            lines.extend(f"  - {problem}" for problem in message.splitlines())
    return "\n".join(lines) + "\n"
