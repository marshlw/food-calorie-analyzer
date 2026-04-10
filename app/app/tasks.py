# app/tasks.py
from pathlib import Path
import logging

from celery import Celery

from .celery_app import celery_app
from .config import settings
from . import ml_service

logger = logging.getLogger(__name__)

# Настройка Celery (можно вынести в celery_app.py, но оставлено для обратной совместимости)
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


@celery_app.task(bind=True, max_retries=3)
def analyze_image_task(self, image_path: str):
    """
    Асинхронная задача анализа изображения.
    Вызывает синхронный метод ml_service.analyze_image_sync
    и удаляет временный файл после обработки.
    """
    path = Path(image_path)
    try:
        logger.info(f"Starting analysis for {image_path}")
        result = ml_service.analyze_image_sync(str(path))
        logger.info(f"Analysis completed for {image_path}")
        return result
    except Exception as e:
        logger.exception(f"Error analyzing {image_path}: {e}")
        # Можно добавить ретрай при необходимости
        raise self.retry(exc=e, countdown=60)
    finally:
        # Удаляем временный файл в любом случае
        try:
            path.unlink(missing_ok=True)
        except Exception as unlink_error:
            logger.warning(f"Could not delete {image_path}: {unlink_error}")