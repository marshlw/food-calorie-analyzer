from celery import Celery
from .config import settings

celery_app = Celery(
    "ai_healthy",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks",  # явная регистрация задач (ВАЖНО для Docker)
    ],
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
    task_time_limit=300,
    task_soft_time_limit=270,
)

# ======================
# AUTO DISCOVERY (backup)
# ======================
celery_app.autodiscover_tasks(["app"])