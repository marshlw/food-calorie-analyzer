from pathlib import Path
import logging
import subprocess
import sys
import uuid
import json
from datetime import datetime

from .celery_app import celery_app
from . import ml_service, models
from .crud import update_task
from .database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
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
        task.updated_at = datetime.utcnow()
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
    except Exception as exc:
        logger.exception("Image analysis failed", extra={"task_id": task_id, "error": str(exc)})
        session.rollback()

        retries_done = getattr(self.request, "retries", 0)
        max_retries = getattr(self, "max_retries", 0) or 0
        final_failure = retries_done >= max_retries

        if final_failure and task:
            update_task(session, task_id, models.TaskStatus.FAILURE, error=str(exc))

        raise
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1)
def retrain_model_task(self):
    """Ретрейн модели. Guard-флаг retrain:queued (ставится в
    crud.create_feedback_sync) гарантирует не более одной задачи
    одновременно; снимаем его в finally, чтобы следующий ретрейн
    мог запуститься после завершения текущего."""
    try:
        logger.info("Starting model retraining")

        # Запускаем generate_dataset.py
        script_path = Path(__file__).parent.parent / "training_data" / "generate_dataset.py"
        result = subprocess.run([sys.executable, str(script_path)], capture_output=True, text=True)

        if result.returncode != 0:
            logger.error(f"Dataset generation failed: {result.stderr}")
            raise Exception(f"Dataset generation failed: {result.stderr}")

        logger.info("Dataset generated successfully")

        # Создаём новую модель в Ollama
        modelfile_path = Path(__file__).parent.parent / "training_data" / "Modelfile"
        new_model_name = f"ai-healthy-{uuid.uuid4().hex[:8]}"  # уникальное имя

        create_result = subprocess.run(["ollama", "create", new_model_name, "-f", str(modelfile_path)], capture_output=True, text=True)

        if create_result.returncode != 0:
            logger.error(f"Model creation failed: {create_result.stderr}")
            raise Exception(f"Model creation failed: {create_result.stderr}")

        logger.info(f"New model created: {new_model_name}")

        # Обновляем модель в ml_service
        ml_service.update_model(new_model_name)

        logger.info("Model retraining completed successfully")

    except Exception as e:
        logger.exception(f"Retraining failed: {e}")
        raise
    finally:
        # Снимаем guard-флаг независимо от результата
        try:
            ml_service.get_redis_client().delete("retrain:queued")
        except Exception:
            pass