from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.schemas.ranking import TopSnippet
from app.services.ranking_service import (
    get_top_by_hook,
    get_top_by_quality,
    get_top_by_readability,
)

router = APIRouter(prefix="/snippets", tags=["snippets"])


@router.get("/top", response_model=list[TopSnippet])
async def get_top_snippets(
    metric: str = Query("quality"),
    limit: int = Query(20, ge=1),
    db: AsyncSession = Depends(get_session),
):
    if metric == "quality":
        return await get_top_by_quality(db, limit=limit)
    elif metric == "hook":
        return await get_top_by_hook(db, limit=limit)
    elif metric == "readability":
        return await get_top_by_readability(db, limit=limit)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported metric",
        )
