# app/tasks.py
import asyncio
import json
from pathlib import Path
from celery import Celery
from .config import settings
from . import ml_service
from . import crud
from .database import async_session_maker
from . import models
import logging
logger = logging.getLogger(__name__)
from .celery_app import celery_app
celery = Celery(
    "tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task
def analyze_image_task(image_path: str):
    from pathlib import Path
    from . import ml_service

    try:
        result = ml_service.analyze_image_sync(image_path)
        Path(image_path).unlink(missing_ok=True)
        return result
    except Exception as e:
        Path(image_path).unlink(missing_ok=True)
        raise e