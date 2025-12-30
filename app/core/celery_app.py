from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "job_recommender",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.services.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="America/Sao_Paulo",
    enable_utc=True,
)
