"""Ошибки создания и поиска конкурса."""

from app.common.exception import AppError, DomainValidationError


class ContestNotFoundError(AppError):
    code = "contest_not_found"
    status = 404


class InvalidContestError(DomainValidationError):
    """Неверные данные конкурса: порядок дедлайнов, тема или описание."""

    code = "invalid_contest"


class DeadlineInPastError(DomainValidationError):
    code = "deadline_in_past"


class DeadlinesOrderError(InvalidContestError):
    """Приём идей должен закрываться раньше голосования (равные дедлайны тоже не подходят)."""

    code = "deadlines_order"
