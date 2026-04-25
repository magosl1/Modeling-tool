"""Celery task definitions (stub for future async jobs)."""
from celery import Celery

from app.core.config import settings

celery_app = Celery("financial_modeler", broker=settings.REDIS_URL)
celery_app.conf.update(
    result_backend=settings.REDIS_URL,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
