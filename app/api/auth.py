from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_session
from app.models.author import Author
from app.models.reader import Reader
from app.schemas.auth import (
    AuthorResponse,
    LoginRequest,
    ReaderResponse,
    RegisterAuthorRequest,
    RegisterReaderRequest,
    TokenResponse,
)
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    hash_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register/author", response_model=AuthorResponse, status_code=status.HTTP_201_CREATED)
async def register_author(payload: RegisterAuthorRequest, db: AsyncSession = Depends(get_session)) -> Author:
    author = Author(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        bio=payload.bio,
    )
    db.add(author)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    await db.refresh(author)
    return author


@router.post("/register/reader", response_model=ReaderResponse, status_code=status.HTTP_201_CREATED)
async def register_reader(payload: RegisterReaderRequest, db: AsyncSession = Depends(get_session)) -> Reader:
    reader = Reader(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
    )
    db.add(reader)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="username or email already exists")
    await db.refresh(reader)
    return reader


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_session)) -> TokenResponse:
    auth_result = await authenticate_user(db, payload.email, payload.password)
    if auth_result is None:
        raise HTTPException(status_code=401, detail="invalid email or password")

    user, user_type = auth_result
    subject = str(user.id)
    return TokenResponse(
        access_token=create_access_token(subject, user_type),
        refresh_token=create_refresh_token(subject, user_type),
    )
