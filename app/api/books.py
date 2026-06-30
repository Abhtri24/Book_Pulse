from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_author, get_session
from app.models.author import Author
from app.schemas.book import BookCreateRequest, BookResponse
from app.schemas.chapter import ChapterCreateRequest, ChapterResponse
from app.schemas.snippet import SnippetCreateRequest, SnippetResponse
from app.services.book_service import (
    chapter_number_exists,
    create_book,
    create_chapter,
    create_snippet,
    get_author_book,
    get_book,
)

router = APIRouter(prefix="/books", tags=["books"])


@router.post("", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
async def create_author_book(
    payload: BookCreateRequest,
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session),
) -> BookResponse:
    return await create_book(db, author, payload)


@router.post("/{book_id}/snippets", response_model=SnippetResponse, status_code=status.HTTP_201_CREATED)
async def upload_snippet(
    book_id: UUID,
    payload: SnippetCreateRequest,
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session),
) -> SnippetResponse:
    book = await get_author_book(db, author, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    return await create_snippet(db, author, book, payload)


@router.post(
    "/{book_id}/chapters",
    response_model=ChapterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_chapter(
    book_id: UUID,
    payload: ChapterCreateRequest,
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session),
) -> ChapterResponse:
    book = await get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="book not found")
    if book.author_id != author.id:
        raise HTTPException(status_code=403, detail="book belongs to another author")
    if await chapter_number_exists(db, book.id, payload.chapter_number):
        raise HTTPException(status_code=409, detail="chapter number already exists")
    try:
        return await create_chapter(db, book, payload)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="chapter number already exists")
