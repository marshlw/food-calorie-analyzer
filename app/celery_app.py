import logging

from celery import Celery
from celery.signals import worker_process_init, worker_shutdown
from .config import settings
from . import ml_service

logger = logging.getLogger(__name__)

celery_app = Celery(
    "ai_healthy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# ======================
# CONFIG
# ======================
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # ======================
    # stability settings
    # ======================
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,

    # защита от зависших задач
    task_time_limit=600,  # retraining может занять время
    task_soft_time_limit=540,
)

@worker_process_init.connect
def init_worker_resources(sender, **kwargs):
    try:
        ml_service.get_http_client()
        ml_service.get_redis_client()
        logger.info("Celery worker resources initialized")
    except Exception as exc:
        logger.warning("Celery worker resource initialization failed", exc_info=exc)


@worker_shutdown.connect
def shutdown_worker_resources(sender, **kwargs):
    try:
        ml_service.close_http_client()
        ml_service.close_redis_client()
        logger.info("Celery worker resources closed")
    except Exception as exc:
        logger.warning("Celery worker shutdown cleanup failed", exc_info=exc)


# ======================
# IMPORT TASKS (ВАЖНО!)
# ======================
# Явно импортируем задачи, чтобы они были зарегистрированы в Celery
from . import tasks  # noqa: F401, E402