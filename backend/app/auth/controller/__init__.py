"""auth.controller — маршруты входа, выхода и профиля."""

from app.auth.controller.dependencies import resolve_request_actor
from app.auth.controller.router import router

__all__ = ["resolve_request_actor", "router"]
