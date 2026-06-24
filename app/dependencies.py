import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.author import Author
from app.models.reader import Reader
from app.services.auth_service import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_db():
        yield session


async def get_current_author(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> Author:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        author_id = uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_exception

    if payload.get("type") != "author":
        raise credentials_exception

    author = await db.get(Author, author_id)
    if author is None:
        raise credentials_exception
    return author


async def get_current_reader(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_session),
) -> Reader:
    """Authenticate a reader from the Bearer JWT token.

    Raises HTTP 401 when the token is absent, expired, or was issued for an
    author account rather than a reader account.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        reader_id = uuid.UUID(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise credentials_exception

    if payload.get("type") != "reader":
        raise credentials_exception

    reader = await db.get(Reader, reader_id)
    if reader is None:
        raise credentials_exception
    return reader
