from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.book import Book, BookStatus, SourcePlatform
from app.schemas.book import BookCreateRequest, BookResponse


def test_book_create_request_requires_external_url():
    with pytest.raises(ValidationError):
        BookCreateRequest(title="Missing Link")


@pytest.mark.parametrize(
    "external_url",
    ["not-a-url", "ftp://example.com/book", "example.com/book", ""],
)
def test_book_create_request_rejects_malformed_external_url(external_url):
    with pytest.raises(ValidationError):
        BookCreateRequest(title="Bad Link", external_url=external_url)


def test_book_response_includes_external_link_fields():
    book = Book(
        id=uuid4(),
        author_id=uuid4(),
        title="Linked Story",
        description="",
        status=BookStatus.draft,
        external_url="https://tapas.io/series/linked-story",
        source_platform=SourcePlatform.tapas,
    )

    response = BookResponse.model_validate(book)

    assert response.external_url == "https://tapas.io/series/linked-story"
    assert response.source_platform == SourcePlatform.tapas
