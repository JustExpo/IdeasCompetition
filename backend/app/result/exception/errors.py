"""Ошибки доступа к итогам."""

from app.common.exception import AppError


class ResultsNotPublishedError(AppError):
    """Сотрудник запросил итоги до финала; организатору они доступны без авторов."""

    code = "results_not_published"
    status = 403
