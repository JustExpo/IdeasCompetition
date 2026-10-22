"""Подача идеи: отпечаток запроса для идемпотентного повтора и результат подачи."""

import hashlib
import json
from dataclasses import dataclass

from app.common.model import ContestId
from app.idea.model.idea import Idea, IdeaContent


def compute_request_hash(contest_id: ContestId, content: IdeaContent) -> bytes:
    """Отпечаток (конкурс, название, описание) нормализованного запроса.

    Повтор с тем же `client_request_id` принимается, только если отпечаток совпал: тот же ключ
    с другим телом или для другого конкурса — ошибка клиента, а не повтор. JSON-массив
    однозначен: «a|b» + «c» и «a» + «b|c» дают разные байты.
    """
    payload = json.dumps([int(contest_id), content.title, content.description], ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).digest()


@dataclass(frozen=True, slots=True)
class SubmittedIdea:
    """`created=False` — повтор уже принятого запроса (в HTTP это 200, а не 201)."""

    idea: Idea
    created: bool
