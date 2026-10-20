"""Ошибки подачи, правки и удаления идеи."""

from app.common.exception import AppError, DomainValidationError


class IdeaNotFoundError(AppError):
    """Идеи нет или она недоступна пользователю.

    Ответ в обоих случаях одинаковый, чтобы не раскрывать существование идеи.
    """

    code = "idea_not_found"
    status = 404


class InvalidIdeaContentError(DomainValidationError):
    code = "invalid_idea"


class SubmissionClosedError(AppError):
    code = "submission_closed"
    status = 409


class StaleIdeaVersionError(AppError):
    """Идею уже изменили в другой вкладке."""

    code = "stale_version"
    status = 409


class IdeaLockedError(AppError):
    """После финала идеи нельзя менять и удалять."""

    code = "idea_locked"
    status = 409


class IdeaLimitReachedError(AppError):
    code = "idea_limit_reached"
    status = 409


class ContestFullError(AppError):
    code = "contest_full"
    status = 409


class IdempotencyKeyReusedError(DomainValidationError):
    """Тот же client_request_id прислан с другим содержимым или для другого конкурса."""

    code = "idempotency_key_reused"
