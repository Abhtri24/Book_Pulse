from fastapi import FastAPI

from app.api import auth, books, health, dashboard
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(books.router)
    app.include_router(dashboard.router)
    return app


app = create_app()
