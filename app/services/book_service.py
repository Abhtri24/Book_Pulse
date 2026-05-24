from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.schemas.book import BookCreateRequest
from app.schemas.snippet import SnippetCreateRequest


async def create_book(db: AsyncSession, author: Author, payload: BookCreateRequest) -> Book:
    book = Book(
        author_id=author.id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return book


async def get_author_book(db: AsyncSession, author: Author, book_id: UUID) -> Book | None:
    result = await db.execute(
        select(Book).where(Book.id == book_id, Book.author_id == author.id)
    )
    return result.scalar_one_or_none()


async def create_snippet(
    db: AsyncSession,
    author: Author,
    book: Book,
    payload: SnippetCreateRequest,
) -> Snippet:
    snippet = Snippet(
        book_id=book.id,
        author_id=author.id,
        content=payload.content,
        chapter_number=payload.chapter_number,
    )
    db.add(snippet)
    await db.commit()
    await db.refresh(snippet)
    return snippet
