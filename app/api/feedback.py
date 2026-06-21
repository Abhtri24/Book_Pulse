from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_author, get_session
from app.models.author import Author
from app.models.book import Book
from app.models.snippet import Snippet
from app.models.snippet_feedback import SnippetFeedback
from app.schemas.feedback import SnippetFeedbackResponse

router = APIRouter(prefix="/books", tags=["feedback"])


@router.get(
    "/{book_id}/snippets/{snippet_id}/feedback",
    response_model=SnippetFeedbackResponse,
)
async def get_snippet_feedback(
    book_id: UUID,
    snippet_id: UUID,
    author: Author = Depends(get_current_author),
    db: AsyncSession = Depends(get_session),
) -> SnippetFeedbackResponse:
    book = await db.get(Book, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="book not found")
    if book.author_id != author.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="book belongs to another author")

    snippet = await db.get(Snippet, snippet_id)
    if snippet is None or snippet.book_id != book.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="snippet not found")

    result = await db.execute(
        select(SnippetFeedback).where(SnippetFeedback.snippet_id == snippet.id)
    )
    feedback = result.scalar_one_or_none()
    if feedback is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="feedback not found")

    return feedback
