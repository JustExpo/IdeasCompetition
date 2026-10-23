from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import (
    CONFIG_EXIT_CODE,
    DEV_FRONTEND_ORIGIN,
    EXAMPLE_ORGANIZER_PASSWORD,
    Settings,
    load_settings,
)

ENV_EXAMPLE = Path(__file__).parents[4] / ".env.example"
STRONG_PASSWORD = "correct-horse-battery-staple"
SECRET_DB_PASSWORD = "zq-db-secret-91"


def base_env(**overrides: str) -> dict[str, str]:
    env = {
        "APP_ENV": "dev",
        "DATABASE_URL": f"postgresql+asyncpg://ideas:{SECRET_DB_PASSWORD}@db:5432/ideas",
        "ORGANIZER_EMAIL": "organizer@example.com",
        "ORGANIZER_PASSWORD": STRONG_PASSWORD,
        "ORGANIZER_NAME": "Организатор",
        "ALLOWED_EMAIL_DOMAINS": "example.com, Corp.Example.org",
        "PUBLIC_BASE_URL": "http://127.0.0.1:8000",
        "SMTP_HOST": "mailpit",
        "SMTP_PORT": "1025",
        "MAIL_FROM": "ideas@example.com",
    }
    env.update(overrides)
    return env


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def apply_env(monkeypatch: pytest.MonkeyPatch, env: dict[str, str]) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)


def build(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    apply_env(monkeypatch, base_env(**overrides))
    return Settings()


def problems_of(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> str:
    with pytest.raises(ValidationError) as caught:
        build(monkeypatch, **overrides)
    return str(caught.value)


def test_valid_dev_settings_are_loaded_with_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build(monkeypatch)
    assert settings.app_env == "dev"
    assert settings.allowed_email_domains == ("example.com", "corp.example.org")
    assert settings.display_tz == "Europe/Moscow"
    assert settings.scheduler_interval_s == 15
    assert settings.web_concurrency == 1
    assert settings.run_scheduler is True
    assert settings.rate_limit_per_ip_enabled is True
    assert settings.test_clock_enabled is False
    assert settings.log_format == "json"


def test_secrets_are_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    shown = repr(build(monkeypatch))
    assert SECRET_DB_PASSWORD not in shown
    assert STRONG_PASSWORD not in shown


def test_env_example_is_valid_for_dev_and_rejected_for_prod(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pairs = [
        line.split("=", 1)
        for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    example = {key: value for key, value in pairs}
    assert example["ORGANIZER_PASSWORD"] == EXAMPLE_ORGANIZER_PASSWORD
    apply_env(monkeypatch, example)
    assert Settings().app_env == "dev"
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://ideas.example.com")
    with pytest.raises(ValidationError, match=r"из \.env\.example"):
        Settings()


@pytest.mark.parametrize("missing", sorted(base_env()))
def test_missing_required_variable_is_reported(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    env = base_env()
    del env[missing]
    apply_env(monkeypatch, env)
    with pytest.raises(ValidationError) as caught:
        Settings()
    assert {tuple(e["loc"]) for e in caught.value.errors()} == {(missing.lower(),)}


@pytest.mark.parametrize("name", ["ORGANIZER_NAME", "SMTP_HOST", "PUBLIC_BASE_URL"])
def test_empty_variable_is_not_the_same_as_default(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    assert name.lower() in problems_of(monkeypatch, **{name: ""})


def test_empty_optional_variable_does_not_fall_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, SCHEDULER_INTERVAL_S="")


@pytest.mark.parametrize("value", ["staging", "", "DEV"])
def test_app_env_must_be_known(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, APP_ENV=value)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u:p@db/ideas",
        "mysql+asyncpg://u:p@db/ideas",
        "postgresql+asyncpg://u:p@/ideas",
        "postgresql+asyncpg://u:p@db",
        "not a url",
    ],
)
def test_database_url_must_be_asyncpg_with_host_and_name(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    assert "DATABASE_URL" in problems_of(monkeypatch, DATABASE_URL=url)


def test_e2e_requires_database_name_suffix(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "_e2e" in problems_of(
        monkeypatch, APP_ENV="e2e", DATABASE_URL="postgresql+asyncpg://u:p@db/ideas"
    )
    settings = build(
        monkeypatch, APP_ENV="e2e", DATABASE_URL="postgresql+asyncpg://u:p@db/ideas_e2e"
    )
    assert settings.app_env == "e2e"


@pytest.mark.parametrize("password", ["short", "x" * 9, "x" * 129])
def test_organizer_password_length_bounds(monkeypatch: pytest.MonkeyPatch, password: str) -> None:
    assert "ORGANIZER_PASSWORD" in problems_of(monkeypatch, ORGANIZER_PASSWORD=password)


@pytest.mark.parametrize("password", ["x" * 10, "x" * 128])
def test_organizer_password_bounds_are_inclusive_in_dev(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    assert build(monkeypatch, ORGANIZER_PASSWORD=password).app_env == "dev"


PROD = {"APP_ENV": "prod", "PUBLIC_BASE_URL": "https://ideas.example.com"}


def test_prod_password_must_be_at_least_16(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "16" in problems_of(monkeypatch, **PROD, ORGANIZER_PASSWORD="x" * 15)
    assert build(monkeypatch, **PROD, ORGANIZER_PASSWORD="x" * 16).app_env == "prod"


def test_prod_rejects_example_password(monkeypatch: pytest.MonkeyPatch) -> None:
    assert ".env.example" in problems_of(
        monkeypatch, **PROD, ORGANIZER_PASSWORD=EXAMPLE_ORGANIZER_PASSWORD
    )


def test_prod_requires_https(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "https" in problems_of(monkeypatch, APP_ENV="prod", ORGANIZER_PASSWORD="x" * 16)


@pytest.mark.parametrize("url", ["ftp://host", "127.0.0.1:8000", "http://", "/relative"])
def test_public_base_url_must_be_http_origin(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    assert "PUBLIC_BASE_URL" in problems_of(monkeypatch, PUBLIC_BASE_URL=url)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TEST_CLOCK_ENABLED", "true"),
        ("RATE_LIMIT_PER_IP_ENABLED", "false"),
    ],
)
@pytest.mark.parametrize("env", ["dev", "prod"])
def test_e2e_only_flags_are_rejected_outside_e2e(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, env: str
) -> None:
    overrides = {"APP_ENV": env, "ORGANIZER_PASSWORD": "x" * 16, name: value}
    if env == "prod":
        overrides["PUBLIC_BASE_URL"] = "https://ideas.example.com"
    assert name in problems_of(monkeypatch, **overrides)


def test_e2e_only_flags_are_allowed_in_e2e(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build(
        monkeypatch,
        APP_ENV="e2e",
        DATABASE_URL="postgresql+asyncpg://u:p@db/ideas_e2e",
        TEST_CLOCK_ENABLED="true",
        RATE_LIMIT_PER_IP_ENABLED="false",
        SEED_DEMO="true",
    )
    assert settings.test_clock_enabled is True
    assert settings.rate_limit_per_ip_enabled is False


def test_seed_demo_is_allowed_in_dev_but_not_prod(monkeypatch: pytest.MonkeyPatch) -> None:
    assert build(monkeypatch, SEED_DEMO="true").seed_demo is True
    assert "SEED_DEMO" in problems_of(
        monkeypatch, **PROD, ORGANIZER_PASSWORD="x" * 16, SEED_DEMO="true"
    )


@pytest.mark.parametrize("value", ["0", "2", "4"])
def test_web_concurrency_must_be_one(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    assert "WEB_CONCURRENCY" in problems_of(monkeypatch, WEB_CONCURRENCY=value)


@pytest.mark.parametrize("value", ["4", "301", "abc", "-1"])
def test_scheduler_interval_bounds(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, SCHEDULER_INTERVAL_S=value)


@pytest.mark.parametrize("value", ["5", "300"])
def test_scheduler_interval_bounds_are_inclusive(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    assert build(monkeypatch, SCHEDULER_INTERVAL_S=value).scheduler_interval_s == int(value)


@pytest.mark.parametrize("value", ["Mars/Base", "", "../etc/passwd", "moscow"])
def test_display_tz_must_be_known_iana_zone(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, DISPLAY_TZ=value)


def test_display_tz_accepts_known_zone(monkeypatch: pytest.MonkeyPatch) -> None:
    assert build(monkeypatch, DISPLAY_TZ="Asia/Tokyo").display_tz == "Asia/Tokyo"


@pytest.mark.parametrize("value", ["", " , ", "localhost", "bad domain.com", "-.com"])
def test_email_domains_must_be_valid_list(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, ALLOWED_EMAIL_DOMAINS=value)


@pytest.mark.parametrize("value", ["0", "65536", "smtp"])
def test_smtp_port_bounds(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    with pytest.raises(ValidationError):
        build(monkeypatch, SMTP_PORT=value)


def test_allowed_origins_include_vite_dev_server_only_in_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dev = build(monkeypatch)
    assert DEV_FRONTEND_ORIGIN in dev.allowed_origins
    e2e = build(monkeypatch, APP_ENV="e2e", DATABASE_URL="postgresql+asyncpg://u:p@db/ideas_e2e")
    assert DEV_FRONTEND_ORIGIN not in e2e.allowed_origins
    prod = build(monkeypatch, **PROD, ORGANIZER_PASSWORD="x" * 16)
    assert prod.allowed_origins == ("https://ideas.example.com",)


E2E_DB = "postgresql+asyncpg://u:p@db/ideas_e2e"


def test_allowed_origins_dev_has_loopback_twin_and_vite(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build(monkeypatch)
    assert settings.allowed_origins == (
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        DEV_FRONTEND_ORIGIN,
    )


def test_allowed_origins_dev_twin_works_both_ways(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build(monkeypatch, PUBLIC_BASE_URL="http://localhost:9000")
    assert settings.allowed_origins[:2] == ("http://localhost:9000", "http://127.0.0.1:9000")


def test_allowed_origins_e2e_has_twin_without_vite(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = build(monkeypatch, APP_ENV="e2e", DATABASE_URL=E2E_DB)
    assert settings.allowed_origins == ("http://127.0.0.1:8000", "http://localhost:8000")


def test_allowed_origins_prod_has_only_own_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    prod = build(monkeypatch, **PROD, ORGANIZER_PASSWORD="x" * 16)
    assert prod.loopback_twin_origin is None
    assert prod.allowed_origins == ("https://ideas.example.com",)


def test_allowed_origins_never_include_twin_for_foreign_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = build(monkeypatch, PUBLIC_BASE_URL="http://ideas.corp.example:8000")
    assert settings.loopback_twin_origin is None
    assert "http://localhost:8000" not in settings.allowed_origins


def test_all_problems_are_reported_and_exit_code_is_2_without_secret_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    bad_password = "tiny"
    apply_env(
        monkeypatch,
        base_env(
            ORGANIZER_PASSWORD=bad_password,
            WEB_CONCURRENCY="3",
            TEST_CLOCK_ENABLED="true",
            DISPLAY_TZ="Mars/Base",
            SMTP_PORT="0",
        ),
    )
    monkeypatch.delenv("MAIL_FROM")
    with pytest.raises(SystemExit) as exit_info:
        load_settings()
    assert exit_info.value.code == CONFIG_EXIT_CODE
    err = capsys.readouterr().err
    for field in ("DISPLAY_TZ", "SMTP_PORT", "MAIL_FROM"):
        assert field in err
    assert SECRET_DB_PASSWORD not in err
    assert bad_password not in err
    assert "Mars/Base" not in err


def test_cross_field_problems_are_all_listed_together(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    apply_env(
        monkeypatch,
        base_env(ORGANIZER_PASSWORD="tiny", WEB_CONCURRENCY="3", TEST_CLOCK_ENABLED="true"),
    )
    with pytest.raises(SystemExit):
        load_settings()
    err = capsys.readouterr().err
    for field in ("ORGANIZER_PASSWORD", "WEB_CONCURRENCY", "TEST_CLOCK_ENABLED"):
        assert field in err
    assert "tiny" not in err


def test_valid_environment_is_loaded_by_load_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_env(monkeypatch, base_env())
    assert load_settings().smtp_port == 1025


def test_unparsable_database_url_is_reported_without_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text = problems_of(monkeypatch, DATABASE_URL="postgresql+asyncpg://u:hidden-pw@[::1/ideas")
    assert "DATABASE_URL" in text
    assert "hidden-pw" not in text


def test_email_domains_accept_ready_sequence_from_code(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_env(monkeypatch, base_env())
    monkeypatch.delenv("ALLOWED_EMAIL_DOMAINS")
    settings = Settings(allowed_email_domains=("example.com", "corp.org"))
    assert settings.allowed_email_domains == ("example.com", "corp.org")
