import asyncio
import logging
import threading
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CeleryAsyncDatabase:
    """Owns async SQLAlchemy resources for a Celery worker process.

    Celery tasks are synchronous callables. Running each task with ``asyncio.run``
    creates a fresh event loop and then closes it, which is unsafe for asyncpg pooled
    connections. This runtime keeps one event loop alive for the worker process and
    creates the async engine/sessionmaker inside that loop.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
        self._lock = threading.Lock()

    def run(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(self._run(coro_factory), loop)
        return future.result()

    @asynccontextmanager
    async def session(self):
        factory = await self._ensure_session_factory()
        session = factory()
        logger.debug("Created Celery AsyncSession id=%s", id(session))
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
            logger.debug("Closed Celery AsyncSession id=%s", id(session))

    def shutdown(self) -> None:
        loop = self._loop
        if loop is None:
            return

        future = asyncio.run_coroutine_threadsafe(self._dispose(), loop)
        future.result(timeout=30)
        loop.call_soon_threadsafe(loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=30)

        self._loop = None
        self._thread = None

    async def _run(self, coro_factory: Callable[[], Awaitable[T]]) -> T:
        return await coro_factory()

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        with self._lock:
            if self._loop is not None and self._loop.is_running():
                return self._loop

            ready = threading.Event()
            loop_holder: dict[str, asyncio.AbstractEventLoop] = {}

            def run_loop() -> None:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop_holder["loop"] = loop
                ready.set()
                logger.info("Started Celery async database event loop id=%s", id(loop))
                loop.run_forever()
                loop.close()
                logger.info("Closed Celery async database event loop id=%s", id(loop))

            thread = threading.Thread(
                target=run_loop,
                name="celery-async-db-loop",
                daemon=True,
            )
            thread.start()
            ready.wait()

            self._loop = loop_holder["loop"]
            self._thread = thread
            return self._loop

    async def _ensure_session_factory(self) -> async_sessionmaker[AsyncSession]:
        running_loop = asyncio.get_running_loop()
        if self._session_factory is not None:
            return self._session_factory

        settings = get_settings()
        self._engine = create_async_engine(
            settings.database_url,
            echo=False,
            future=True,
            pool_pre_ping=True,
        )
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info(
            "Created Celery async engine id=%s on event loop id=%s",
            id(self._engine),
            id(running_loop),
        )
        return self._session_factory

    async def _dispose(self) -> None:
        if self._engine is not None:
            logger.info("Disposing Celery async engine id=%s", id(self._engine))
            await self._engine.dispose()
        self._engine = None
        self._session_factory = None


celery_async_db = CeleryAsyncDatabase()


def run_worker_async(coro_factory: Callable[[], Awaitable[T]]) -> T:
    return celery_async_db.run(coro_factory)


@asynccontextmanager
async def worker_session():
    async with celery_async_db.session() as session:
        yield session


def shutdown_worker_database() -> None:
    celery_async_db.shutdown()
