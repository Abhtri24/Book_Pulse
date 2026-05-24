from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_author, get_session
from app.models.author import Author
from app.schemas.book import BookCreateRequest, BookResponse
from app.schemas.snippet import SnippetCreateRequest, SnippetResponse
from app.services.book_service import create_book, create_snippet, get_author_book

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
