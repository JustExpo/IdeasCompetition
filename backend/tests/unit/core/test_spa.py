"""Раздача SPA и экспорт OpenAPI (IC-015): fallback на index.html, 404 для /api, CSP."""

import json
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

from app.cli import build_openapi_document, export_openapi, main, render_openapi
from app.core.config import Settings
from app.core.middleware import CONTENT_SECURITY_POLICY
from app.main import create_app
from tests.fakes import ReadyDatabase

from .test_config import apply_env, base_env, clean_env  # noqa: F401 — clean_env: autouse-фикстура

ORIGIN = "http://127.0.0.1:8000"
DB_URL = "postgresql+asyncpg://ideas@127.0.0.1:1/ideas"
INDEX_HTML = "<!doctype html><title>SPA</title>"


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    (root / "assets" / "index-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("не отдавать", encoding="utf-8")
    return root


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch, dist: Path) -> FastAPI:
    apply_env(monkeypatch, base_env())
    return create_app(Settings(), database=ReadyDatabase(DB_URL), spa_dir=dist)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as http:
        yield http


@pytest.mark.parametrize("path", ["/", "/contests/1", "/login", "/some/deep/client/route"])
async def test_client_routes_return_index_html(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["Cache-Control"] == "no-cache"


async def test_hashed_asset_is_served_and_cached_forever(client: httpx.AsyncClient) -> None:
    response = await client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.text == "console.log(1)"
    assert "immutable" in response.headers["Cache-Control"]


async def test_missing_asset_falls_back_to_index_html(client: httpx.AsyncClient) -> None:
    response = await client.get("/assets/missing.js")

    assert response.status_code == 200
    assert response.text == INDEX_HTML


async def test_csp_and_security_headers_on_spa_response(client: httpx.AsyncClient) -> None:
    response = await client.get("/")

    assert response.headers["Content-Security-Policy"] == CONTENT_SECURITY_POLICY
    assert "script-src 'self'" in CONTENT_SECURITY_POLICY
    assert "frame-ancestors 'none'" in CONTENT_SECURITY_POLICY
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Referrer-Policy"] == "no-referrer"


@pytest.mark.parametrize("path", ["/api/unknown", "/api/auth/unknown", "/api"])
async def test_unknown_api_path_is_404_problem_json(client: httpx.AsyncClient, path: str) -> None:
    response = await client.get(path)

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_found"
    assert response.headers["Cache-Control"] == "no-store"


async def test_unknown_api_path_with_post_is_also_404(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/unknown", headers={"Origin": ORIGIN})

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_unsafe_method_on_spa_path_is_405_problem_json(client: httpx.AsyncClient) -> None:
    response = await client.post("/contests/1", headers={"Origin": ORIGIN})

    assert response.status_code == 405
    assert response.json()["code"] == "method_not_allowed"


async def test_existing_api_routes_are_not_shadowed(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "path", ["/../secret.txt", "/assets/../../secret.txt", "/%2e%2e/secret.txt", "/%00"]
)
async def test_path_traversal_never_leaves_spa_directory(
    client: httpx.AsyncClient, path: str
) -> None:
    response = await client.get(path)

    assert "не отдавать" not in response.text
    assert response.status_code in (200, 404)


async def test_head_request_to_spa_path(client: httpx.AsyncClient) -> None:
    response = await client.head("/contests/1")

    assert response.status_code == 200
    assert response.content == b""


def test_missing_index_html_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    apply_env(monkeypatch, base_env())

    with pytest.raises(FileNotFoundError):
        create_app(Settings(), database=ReadyDatabase(DB_URL), spa_dir=tmp_path)


def test_spa_is_not_mounted_without_directory(monkeypatch: pytest.MonkeyPatch) -> None:
    apply_env(monkeypatch, base_env())
    application = create_app(Settings(), database=ReadyDatabase(DB_URL))

    assert all(getattr(route, "path", "") != "/{full_path:path}" for route in application.routes)


def test_openapi_export_is_stable_and_does_not_leak_catch_all(tmp_path: Path) -> None:
    document = build_openapi_document()
    paths = set(document["paths"])

    assert {"/api/auth/login", "/api/auth/register", "/api/auth/me"} <= paths
    assert all(path.startswith("/api") for path in paths)

    first = render_openapi(document)
    second = render_openapi(build_openapi_document())
    assert first == second
    assert first.endswith("}\n")
    assert json.loads(first) == document

    target = tmp_path / "nested" / "openapi.json"
    export_openapi(target)
    assert target.read_text(encoding="utf-8") == first


def test_cli_export_openapi_command_writes_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "openapi.json"

    assert main(["export-openapi", "--output", str(target)]) == 0

    assert json.loads(target.read_text(encoding="utf-8"))["openapi"].startswith("3.")
    assert str(target) in capsys.readouterr().out


def test_openapi_export_does_not_read_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "not-a-url")
    monkeypatch.setenv("APP_ENV", "prod")

    assert "/api/health" in build_openapi_document()["paths"]
