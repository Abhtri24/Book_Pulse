from app.config import get_settings
from app.tasks.celery_app import create_celery_app


def test_celery_app_uses_redis_settings(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/3")
    get_settings.cache_clear()

    app = create_celery_app()

    assert app.main == "bookpulse"
    assert app.conf.broker_url == "redis://redis:6379/3"
    assert app.conf.result_backend == "redis://redis:6379/3"
    get_settings.cache_clear()


def test_celery_app_uses_json_serialization():
    app = create_celery_app()

    assert app.conf.task_serializer == "json"
    assert app.conf.result_serializer == "json"
    assert app.conf.accept_content == ["json"]
