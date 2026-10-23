"""auth.controller — маршруты входа, выхода и профиля."""

from app.auth.controller.dependencies import request_session_key, resolve_request_actor
from app.auth.controller.router import router

__all__ = ["request_session_key", "resolve_request_actor", "router"]
