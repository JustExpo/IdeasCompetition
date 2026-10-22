"""auth.model — доменные модели входа и сессий."""

from app.auth.model.session import Session
from app.common.model import Actor  # живёт в common: политики модулей ниже auth его тоже используют

__all__ = ["Actor", "Session"]
