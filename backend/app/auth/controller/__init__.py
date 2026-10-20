"""auth.controller — маршруты входа, выхода и профиля."""

from app.auth.controller.dependencies import get_current_actor, resolve_request_actor
from app.auth.controller.router import router

__all__ = ["get_current_actor", "resolve_request_actor", "router"]
