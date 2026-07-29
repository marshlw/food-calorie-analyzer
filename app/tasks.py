from pathlib import Path
import logging
import shutil
import subprocess
import sys
import time
import uuid
import json
from datetime import datetime, timezone

from .celery_app import celery_app
from .config import settings
from . import ml_service, models
from .crud import update_task
from .database import SessionLocal

logger = logging.getLogger(__name__)


# Ретраи делаем ВРУЧНУЮ (self.retry), а не через autoretry_for=(Exception,):
# нужно различать временный сбой провайдера (ретраим) и постоянную ошибку
# вроде пропавшего файла (ретрай бессмыслен, сразу FAILURE + возврат попытки).
@celery_app.task(
    bind=True,
    max_retries=3,
    soft_time_limit=540,
    time_limit=600,
)
def analyze_image_task(self, task_id: str, file_path: str):
    """Анализирует загруженное изображение пищи и возвращает состав КБЖУ."""
    session = SessionLocal()
    task = None

    try:
        logger.info(
            "Starting image analysis",
            extra={"task_id": task_id, "file_path": file_path},
        )
        task = session.query(models.Task).filter(models.Task.id == task_id).first()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        if task.status == models.TaskStatus.SUCCESS and task.result_json:
            logger.info(
                "Skipping analysis because task is already successful",
                extra={"task_id": task_id},
            )
            return json.loads(task.result_json)

        task.status = models.TaskStatus.PROCESSING
        # M-7: колонка DateTime(timezone=True) — пишем aware-время.
        # naive utcnow() Postgres трактует как локальное время сессии,
        # из-за чего created_at/updated_at расходились между собой.
        task.updated_at = datetime.now(timezone.utc)
        session.commit()

        result = ml_service.analyze_image_sync(file_path)
        logger.info(
            "Analysis completed",
            extra={"task_id": task_id, "food": result.get("food", "unknown")},
        )

        update_task(session, task_id, models.TaskStatus.SUCCESS, result=result, error=None)

        # По умолчанию фото сохраняем — оно нужно на экране «Результат анализа»
        # и для обратной связи. Удаление включается флагом DELETE_UPLOAD_AFTER_ANALYSIS.
        from .config import settings as _settings
        if getattr(_settings, "DELETE_UPLOAD_AFTER_ANALYSIS", False):
            try:
                p = Path(file_path).resolve()
                upload_dir = Path(ml_service.UPLOAD_DIR).resolve()
                if upload_dir in p.parents or p == upload_dir:
                    if p.exists() and p.is_file():
                        p.unlink()
                        logger.info("Deleted uploaded file", extra={"file_path": str(p)})
                else:
                    logger.warning("Skipping delete of file outside upload dir", extra={"file_path": str(p)})
            except Exception as cleanup_error:
                logger.warning(
                    "Failed to delete uploaded file",
                    extra={"file_path": file_path, "error": str(cleanup_error)},
                )

        return result

    except ml_service.AnalysisPermanentError as exc:
        # Ретрай не поможет (файла нет / он битый) — сразу финализируем
        logger.warning("Image analysis failed permanently", extra={"task_id": task_id, "error": str(exc)})
        session.rollback()
        _fail_analysis_task(session, task, task_id, str(exc))
        return {"status": "failure", "error": str(exc)}

    except Exception as exc:
        logger.exception("Image analysis failed", extra={"task_id": task_id, "error": str(exc)})
        session.rollback()

        retries_done = getattr(self.request, "retries", 0) or 0
        if retries_done < self.max_retries:
            # Экспоненциальный backoff: 30 с, 60 с, 120 с (потолок 600 с).
            countdown = min(30 * (2 ** retries_done), 600)
            logger.info(
                "Retrying image analysis",
                extra={"task_id": task_id, "retry": retries_done + 1, "countdown": countdown},
            )
            raise self.retry(exc=exc, countdown=countdown)

        _fail_analysis_task(session, task, task_id, str(exc))
        raise
    finally:
        session.close()


def _fail_analysis_task(session, task, task_id: str, error: str) -> None:
    """Помечает задачу FAILURE и ВОЗВРАЩАЕТ пользователю попытку из дневного
    лимита: списывать её за анализ, который мы так и не выполнили, нечестно."""
    if task is None:
        return

    user_id = task.user_id
    try:
        update_task(session, task_id, models.TaskStatus.FAILURE, error=error)
    except Exception as exc:
        logger.warning("Unable to mark task as failed", extra={"task_id": task_id}, exc_info=exc)

    try:
        from . import rate_limit
        rate_limit.refund_ai_daily(user_id)
        logger.info("Refunded AI daily attempt", extra={"task_id": task_id, "user_id": user_id})
    except Exception as exc:
        logger.warning("Unable to refund AI attempt", extra={"task_id": task_id}, exc_info=exc)


@celery_app.task(bind=True, max_retries=1, time_limit=1800, soft_time_limit=1740)
def retrain_model_task(self):
    """Ретрейн модели по накопленным фидбекам.

    ВЫКЛЮЧЕН по умолчанию (settings.RETRAIN_ENABLED): в прод-образе нет
    бинарника ollama, MODEL_PROVIDER=yandex. Триггер стоит в
    crud.create_feedback_sync и тоже проверяет флаг.

    Guard-флаг retrain:queued (SET NX + TTL, ставится в
    crud.create_feedback_sync) не даёт запустить две задачи сразу.
    ВАЖНО: при НЕУДАЧЕ флаг НЕ снимаем — пусть истечёт по TTL. Иначе
    следующий же фидбек ставил бы в очередь заново падающую задачу
    (pending_count не опускается ниже 10, пока фидбеки не разобраны),
    и очередь наполнялась бы бесконечно. TTL здесь работает как backoff.
    """
    from .config import settings as _settings

    if not _settings.RETRAIN_ENABLED:
        logger.info("Retraining is disabled (RETRAIN_ENABLED=false), skipping")
        _release_retrain_guard()
        return {"status": "disabled"}

    try:
        logger.info("Starting model retraining")

        # Путь к скриптам: __file__ = /app/app/tasks.py, а training_data
        # лежит рядом с ним (/app/app/training_data), НЕ на уровень выше.
        training_dir = Path(__file__).parent / "training_data"

        script_path = training_dir / "generate_dataset.py"
        if not script_path.is_file():
            raise FileNotFoundError(f"Dataset generator not found: {script_path}")

        # timeout обязателен: без него зависший subprocess держит слот
        # воркера до task_time_limit и переживает SIGTERM при деплое.
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True, text=True, timeout=600,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Dataset generation failed: {result.stderr}")

        logger.info("Dataset generated successfully")

        modelfile_path = training_dir / "Modelfile"
        if not modelfile_path.is_file():
            raise FileNotFoundError(f"Modelfile not found: {modelfile_path}")

        new_model_name = f"ai-healthy-{uuid.uuid4().hex[:8]}"  # уникальное имя

        create_result = subprocess.run(
            ["ollama", "create", new_model_name, "-f", str(modelfile_path)],
            capture_output=True, text=True, timeout=900,
        )

        if create_result.returncode != 0:
            raise RuntimeError(f"Model creation failed: {create_result.stderr}")

        logger.info("New model created: %s", new_model_name)

        ml_service.update_model(new_model_name)
        logger.info("Model retraining completed successfully")

        # Успех — снимаем guard, следующий ретрейн можно запускать сразу
        _release_retrain_guard()
        return {"status": "ok", "model": new_model_name}

    except Exception as e:
        # Guard НЕ снимаем — пусть дотикает TTL и работает как backoff
        logger.exception("Retraining failed: %s", e)
        raise


def _release_retrain_guard() -> None:
    try:
        ml_service.get_redis_client().delete("retrain:queued")
    except Exception as exc:
        logger.warning("Unable to release retrain guard", exc_info=exc)


# ==================== УБОРКА ДИСКА ====================

@celery_app.task(time_limit=1800, soft_time_limit=1740)
def cleanup_uploads_task():
    """Удаляет из UPLOAD_DIR файлы, которые больше не нужны.

    Без этого том uploads растёт монотонно (~3 ГБ/сутки при 5000 DAU) и
    ВМ упирается в 'No space left on device' — первым падает Postgres.

    Удаляем файл, если он старше UPLOAD_RETENTION_DAYS ЛИБО «осиротел»
    (на него не ссылается ни tasks.image_path, ни meal_entries.photo_path,
    ни feedback.image_path). Сюда же попадают промежуточные p_*.jpg,
    которые оставляет ml_service.preprocess — на них не ссылается никто.

    Записи в БД НЕ трогаем: у приёма пищи остаются КБЖУ, пропадает только
    картинка. photo_url при этом продолжает отдавать подписанную ссылку —
    она вернёт 404, поэтому <img> на фронте обрабатывает onError и
    показывает плашку «нет фото» (MealDetail.tsx).

    Свежие файлы (младше суток) не трогаем НИКОГДА, даже если они
    выглядят осиротевшими: между сохранением файла и коммитом строки в
    БД есть окно, и уборка не должна в него попадать.
    """
    upload_dir = Path(settings.UPLOAD_DIR)
    if not upload_dir.is_dir():
        logger.warning("Upload dir does not exist: %s", upload_dir)
        return {"status": "skipped"}

    now = time.time()
    retention_seconds = settings.UPLOAD_RETENTION_DAYS * 86400
    grace_seconds = 86400  # неприкосновенный период для свежих файлов

    session = SessionLocal()
    try:
        referenced = _collect_referenced_paths(session)
    finally:
        session.close()

    deleted = 0
    freed_bytes = 0
    errors = 0

    for path in upload_dir.iterdir():
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            age = now - stat.st_mtime

            if age < grace_seconds:
                continue

            expired = age > retention_seconds
            orphaned = str(path) not in referenced and path.name not in referenced

            if not (expired or orphaned):
                continue

            size = stat.st_size
            path.unlink()
            deleted += 1
            freed_bytes += size
        except FileNotFoundError:
            continue  # удалили параллельно — не считаем ошибкой
        except OSError as exc:
            errors += 1
            logger.warning("Unable to remove upload", extra={"path": str(path), "error": str(exc)})

    free_gb = _log_disk_usage(upload_dir)

    logger.info(
        "Upload cleanup finished",
        extra={
            "deleted": deleted,
            "freed_mb": round(freed_bytes / 1024 / 1024, 1),
            "errors": errors,
            "free_gb": free_gb,
        },
    )
    return {"deleted": deleted, "freed_bytes": freed_bytes, "errors": errors}


def _collect_referenced_paths(session) -> set:
    """Все пути к фото, на которые ссылается БД.

    Кладём и полный путь, и одно имя файла: исторически в колонках
    встречаются оба варианта (абсолютный путь и просто имя).
    """
    referenced = set()

    columns = (
        models.Task.image_path,
        models.MealEntry.photo_path,
        models.Feedback.image_path,
    )
    for column in columns:
        try:
            for (value,) in session.query(column).filter(column.isnot(None)).yield_per(1000):
                if not value:
                    continue
                referenced.add(value)
                referenced.add(Path(value).name)
        except Exception as exc:
            # Не смогли прочитать — считаем ВСЁ занятым, чтобы не удалить лишнего
            logger.error("Unable to read photo references, aborting cleanup", exc_info=exc)
            raise

    return referenced


def _log_disk_usage(path: Path) -> float:
    """Свободное место на томе в ГБ; ниже порога — ERROR для алерта."""
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        logger.warning("Unable to read disk usage", exc_info=exc)
        return -1.0

    free_gb = round(usage.free / 1024 ** 3, 2)
    if free_gb < settings.UPLOAD_DISK_FREE_ALERT_GB:
        logger.error(
            "Low disk space on uploads volume",
            extra={"free_gb": free_gb, "threshold_gb": settings.UPLOAD_DISK_FREE_ALERT_GB},
        )
    return free_gb