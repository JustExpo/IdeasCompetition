from datetime import timedelta
from uuid import uuid4

import pytest

from app.common.exception import DomainValidationError
from app.common.model import ContestId, IdeaId, UserId
from app.idea.exception import InvalidIdeaContentError
from app.idea.model import Idea, IdeaContent
from tests.unit.conftest import T0


def test_content_is_normalized() -> None:
    content = IdeaContent.create("  Café  ", "\n Описание \n")
    assert content.title == "Café"  # NFC: e + combining acute → é
    assert content.description == "Описание"


@pytest.mark.parametrize(
    ("title", "description"),
    [
        ("", "описание"),
        ("   ", "описание"),
        ("x" * 201, "описание"),
        ("название", ""),
        ("название", "x" * 10_001),
        ("на\nзвание", "описание"),  # перевод строки в названии запрещён
        ("назв‮ание", "описание"),  # RLO подделывает отображение текста
        ("название", "опи\x00сание"),
        ("название", "опи​сание"),  # zero-width space
    ],
)
def test_content_rejects_invalid(title: str, description: str) -> None:
    with pytest.raises(InvalidIdeaContentError):
        IdeaContent.create(title, description)


def test_content_accepts_limits_and_multiline_description() -> None:
    content = IdeaContent.create("x" * 200, "строка 1\n\tстрока 2" + "x" * 9_982)
    assert len(content.description) == 10_000


def idea(**overrides: object) -> Idea:
    fields: dict[str, object] = dict(
        id=IdeaId(uuid4()),
        contest_id=ContestId(1),
        author_id=UserId(7),
        content=IdeaContent.create("Название", "Описание"),
        submitted_at=T0,
        updated_at=T0,
    )
    fields.update(overrides)
    return Idea(**fields)  # type: ignore[arg-type]


def test_idea_invariants() -> None:
    assert idea().is_authored_by(UserId(7))
    assert not idea().is_authored_by(UserId(8))
    with pytest.raises(DomainValidationError):
        idea(updated_at=T0 - timedelta(seconds=1))
    with pytest.raises(DomainValidationError):
        idea(version=0)
    with pytest.raises(DomainValidationError):
        idea(submitted_at=T0.replace(tzinfo=None))


def test_repr_hides_author_and_text() -> None:
    text = repr(idea(content=IdeaContent.create("Секретное название", "Секретное описание")))
    assert "author_id" not in text
    assert "Секретное" not in text
