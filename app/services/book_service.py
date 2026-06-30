from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.author import Author
from app.models.book import Book
from app.models.chapter import Chapter
from app.models.snippet import Snippet
from app.schemas.book import BookCreateRequest
from app.schemas.chapter import ChapterCreateRequest
from app.schemas.snippet import SnippetCreateRequest


async def create_book(db: AsyncSession, author: Author, payload: BookCreateRequest) -> Book:
    book = Book(
        author_id=author.id,
        title=payload.title,
        description=payload.description,
        status=payload.status,
        external_url=payload.external_url,
        source_platform=payload.source_platform,
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


async def get_book(db: AsyncSession, book_id: UUID) -> Book | None:
    return await db.get(Book, book_id)


async def chapter_number_exists(
    db: AsyncSession,
    book_id: UUID,
    chapter_number: int,
) -> bool:
    result = await db.execute(
        select(Chapter.id).where(
            Chapter.book_id == book_id,
            Chapter.chapter_number == chapter_number,
        )
    )
    return result.scalar_one_or_none() is not None


async def create_chapter(
    db: AsyncSession,
    book: Book,
    payload: ChapterCreateRequest,
) -> Chapter:
    chapter = Chapter(
        book_id=book.id,
        chapter_number=payload.chapter_number,
        title=payload.title,
        content=payload.content,
    )
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def create_snippet(
    db: AsyncSession,
    author: Author,
    book: Book,
    payload: SnippetCreateRequest,
    enqueue_processing: bool = True,
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
    if enqueue_processing:
        from app.tasks.snippet_pipeline import process_snippet

        process_snippet.delay(str(snippet.id))
    return snippet
