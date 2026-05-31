from pathlib import Path

import yaml


def test_docker_compose_defines_pipeline_services():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())

    services = compose["services"]
    assert {"app", "worker", "redis", "qdrant"}.issubset(services)
    assert services["redis"]["image"] == "redis:7-alpine"
    assert services["qdrant"]["image"] == "qdrant/qdrant:v1.12.5"


def test_app_and_worker_share_dev_image_build():
    compose = yaml.safe_load(Path("docker-compose.yml").read_text())
    services = compose["services"]

    assert services["app"]["build"] == services["worker"]["build"]
    assert services["app"]["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert services["worker"]["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert services["worker"]["command"].startswith("celery -A app.tasks.celery_app")
