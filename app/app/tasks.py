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


@celery.task(bind=True)
def analyze_image_task(self, task_id: str, user_id: int, image_path: str, file_hash: str):
    """Задача Celery для анализа изображения"""
    try:
        # Обновляем статус задачи в БД через синхронный вызов (так как Celery не поддерживает asyncio напрямую)
        # Можно использовать run_in_executor или синхронный доступ к БД
        # Для упрощения здесь используем синхронный вариант (создадим отдельную синхронную сессию)
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from .database import DATABASE_URL

        # Создаём синхронный движок и сессию
        sync_engine = create_engine(DATABASE_URL.replace("postgresql+asyncpg", "postgresql"))
        SyncSession = sessionmaker(sync_engine)

        with SyncSession() as db:
            # Обновляем статус на PROCESSING
            crud.update_task_sync(db, task_id, models.TaskStatus.PROCESSING)

            # Вызываем ML анализ (предполагаем, что ml_service имеет синхронную функцию)
            result = ml_service.analyze_image_sync(image_path)

            # Кэшируем в Redis (если нужно)
            # ...

            # Сохраняем результат
            crud.update_task_sync(db, task_id, models.TaskStatus.SUCCESS, result=result)

            # Удаляем временный файл
            Path(image_path).unlink(missing_ok=True)

        return result

    except Exception as e:
        # В случае ошибки обновляем статус
        with SyncSession() as db:
            crud.update_task_sync(db, task_id, models.TaskStatus.FAILURE, error=str(e))
        # Удаляем файл
        Path(image_path).unlink(missing_ok=True)
        raise