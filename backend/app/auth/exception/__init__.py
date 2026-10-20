"""auth.exception — исключения входа и проверки прав."""

from app.auth.exception.errors import (
    AuthenticationRequiredError,
    ForbiddenError,
    InvalidCredentialsError,
)

__all__ = ["AuthenticationRequiredError", "ForbiddenError", "InvalidCredentialsError"]
