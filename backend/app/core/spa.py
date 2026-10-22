"""Раздача собранного SPA тем же процессом (CLAUDE.md §3.3, Р1).

Файл из каталога сборки отдаётся как есть, любой другой путь вне `/api` — `index.html`, чтобы
клиентский маршрутизатор открывал `/contests/1` по прямой ссылке. Неизвестный путь `/api/…`
остаётся ошибкой 404 в формате problem+json: его даёт общий обработчик ошибок.
"""

from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.access import API_PREFIX

# Имена файлов `assets/*` содержат хэш содержимого, поэтому их можно кэшировать навсегда;
# `index.html` ссылается на актуальные имена и должен перечитываться всегда.
_ASSET_CACHE = "public, max-age=31536000, immutable"
_INDEX_CACHE = "no-cache"
_SPA_METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _is_api_path(path: str) -> bool:
    return path == API_PREFIX or path.startswith(API_PREFIX + "/")


def _find_file(root: Path, relative: str) -> Path | None:
    """Файл внутри `root` или `None`; `..` и символические ссылки наружу не пропускаются."""
    if not relative:
        return None
    try:
        candidate = (root / relative).resolve()
    except (ValueError, OSError):  # например, нулевой байт в пути
        return None
    if candidate.is_file() and candidate.is_relative_to(root):
        return candidate
    return None


def install_spa(app: FastAPI, directory: Path) -> None:
    """Добавить в приложение раздачу SPA; вызывается после регистрации всех маршрутов `/api`."""
    root = directory.resolve()
    index = root / "index.html"
    if not index.is_file():
        raise FileNotFoundError(f"В каталоге SPA нет index.html: {root}")

    async def serve_spa(request: Request, full_path: str) -> Response:
        # Все методы ловим сами, иначе POST на неизвестный /api/… получил бы 405, а не 404.
        if _is_api_path("/" + full_path):
            raise StarletteHTTPException(404)
        if request.method not in ("GET", "HEAD"):
            raise StarletteHTTPException(405)
        found = _find_file(root, full_path)
        if found is not None:
            cache = _ASSET_CACHE if full_path.startswith("assets/") else _INDEX_CACHE
            return FileResponse(found, headers={"Cache-Control": cache})
        return FileResponse(index, headers={"Cache-Control": _INDEX_CACHE})

    app.add_api_route("/{full_path:path}", serve_spa, methods=_SPA_METHODS, include_in_schema=False)
