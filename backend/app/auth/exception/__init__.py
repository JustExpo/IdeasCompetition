"""auth.exception — исключения входа."""

from app.auth.exception.errors import (
    InvalidCredentialsError,
    TooManyAttemptsError,
    TooManyLoginAttemptsError,
    TooManyRegistrationsError,
)

__all__ = [
    "InvalidCredentialsError",
    "TooManyAttemptsError",
    "TooManyLoginAttemptsError",
    "TooManyRegistrationsError",
]
