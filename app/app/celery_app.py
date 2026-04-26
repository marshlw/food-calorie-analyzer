from celery import Celery
from .config import settings

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

# ======================
# IMPORT TASKS (ВАЖНО!)
# ======================
# Явно импортируем задачи, чтобы они были зарегистрированы в Celery
from . import tasks  # noqa: F401, E402