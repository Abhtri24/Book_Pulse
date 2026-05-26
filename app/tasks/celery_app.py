from celery import Celery

from app.config import get_settings


def create_celery_app() -> Celery:
    settings = get_settings()
    celery_app = Celery(
        "bookpulse",
        broker=settings.redis_url,
        backend=settings.redis_url,
        include=["app.tasks.snippet_pipeline"],
    )
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
    return celery_app


celery_app = create_celery_app()
