"""Схемы запросов и ответов входа."""

from pydantic import BaseModel, ConfigDict, Field

from app.user.model import User


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Длины заданы лишь как защита от гигантских значений (тело ограничено 64 КБ);
    # правила пароля проверяются при установке пароля, а не при входе.
    email: str = Field(min_length=1, max_length=254)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class UserResponse(BaseModel):
    """Профиль вошедшего: своя учётная запись, поэтому e-mail показывается."""

    model_config = ConfigDict(extra="forbid")

    id: int
    email: str
    name: str
    role: str

    @classmethod
    def from_user(cls, user: User) -> "UserResponse":
        return cls(id=user.id, email=user.email, name=user.name, role=user.role.value)
