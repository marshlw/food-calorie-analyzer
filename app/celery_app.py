import logging

from celery import Celery
from celery.schedules import crontab
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

    # Общий лимит — под анализ фото (Yandex Vision, 20-45 с). Ретрейну нужно
    # больше, поэтому у него собственные limits в декораторе задачи.
    # ОГОВОРКА: прод-воркер работает на пуле потоков (--pool=threads), а он
    # эти лимиты не применяет — celery умеет прерывать задачи только в
    # префорке. Значения оставлены для префорк-запусков (dev, отдельный
    # воркер ретрейна). Реальный потолок в проде задают таймауты httpx
    # (MODEL_TIMEOUT_SECONDS) и ограничение MAX_IMAGE_PIXELS.
    task_time_limit=180,
    task_soft_time_limit=150,

    # ======================
    # ОЧЕРЕДИ
    # ======================
    # Разводим по очередям, чтобы редкая тяжёлая задача (ретрейн, уборка
    # диска) не занимала слоты, в которых пользователи ждут анализ фото.
    # Воркеры слушают конкретные очереди — см. docker-compose.prod.yml.
    task_default_queue="analyze",
    task_routes={
        "app.tasks.analyze_image_task": {"queue": "analyze"},
        "app.tasks.retrain_model_task": {"queue": "retrain"},
        "app.tasks.cleanup_uploads_task": {"queue": "maintenance"},
    },
)

# ======================
# РАСПИСАНИЕ (celery beat)
# ======================
# Уборка диска: том uploads растёт монотонно (~3 ГБ/сутки при 5000 DAU),
# без этого ВМ упирается в "No space left on device" за пару недель,
# и первым падает Postgres.
celery_app.conf.beat_schedule = {
    "cleanup-uploads-nightly": {
        "task": "app.tasks.cleanup_uploads_task",
        # 03:20 UTC — вне пиков приёмов пищи
        "schedule": crontab(hour=3, minute=20),
        "options": {"queue": "maintenance", "expires": 3600},
    },
}

# Прогрев ресурсов при старте префорк-процесса. На пуле потоков
# (--pool=threads, прод) этот сигнал НЕ приходит — и это нормально:
# get_http_client/get_redis_client создают клиентов лениво под
# _resource_lock, первая задача просто заплатит несколько миллисекунд.
# Оба клиента потокобезопасны, один экземпляр обслуживает все потоки.
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