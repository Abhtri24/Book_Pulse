"""Reader feed routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_reader, get_session
from app.models.reader import Reader
from app.schemas.feed import FeedResponse
from app.services.feed_service import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    build_cold_start_feed_response,
    build_feed_response,
)

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=FeedResponse)
async def get_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    reader: Reader = Depends(get_current_reader),
    db: AsyncSession = Depends(get_session),
) -> FeedResponse:
    return await build_feed_response(
        db,
        preference_vector=reader.preference_vector,
        page=page,
        page_size=page_size,
    )


@router.get("/cold", response_model=FeedResponse)
async def get_cold_feed(
    page: int = Query(1, ge=1),
    page_size: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    _reader: Reader = Depends(get_current_reader),
    db: AsyncSession = Depends(get_session),
) -> FeedResponse:
    return await build_cold_start_feed_response(
        db,
        page=page,
        page_size=page_size,
    )
