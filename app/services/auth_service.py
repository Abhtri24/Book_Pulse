from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.author import Author
from app.models.reader import Reader

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_token(
    subject: str,
    user_type: Literal["author", "reader"],
    expires_delta: timedelta,
) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "type": user_type, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(subject: str, user_type: Literal["author", "reader"]) -> str:
    settings = get_settings()
    return create_token(
        subject=subject,
        user_type=user_type,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(subject: str, user_type: Literal["author", "reader"]) -> str:
    settings = get_settings()
    return create_token(
        subject=subject,
        user_type=user_type,
        expires_delta=timedelta(days=settings.refresh_token_expire_days),
    )


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise ValueError("invalid token") from exc


async def get_author_by_email(db: AsyncSession, email: str) -> Author | None:
    result = await db.execute(select(Author).where(Author.email == email))
    return result.scalar_one_or_none()


async def get_reader_by_email(db: AsyncSession, email: str) -> Reader | None:
    result = await db.execute(select(Reader).where(Reader.email == email))
    return result.scalar_one_or_none()


async def authenticate_user(db: AsyncSession, email: str, password: str) -> tuple[Author | Reader, str] | None:
    author = await get_author_by_email(db, email)
    if author and verify_password(password, author.password_hash):
        return author, "author"

    reader = await get_reader_by_email(db, email)
    if reader and verify_password(password, reader.password_hash):
        return reader, "reader"

    return None
