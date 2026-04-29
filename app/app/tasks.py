from pathlib import Path
import logging
import subprocess
import sys
import uuid
import json
from datetime import datetime

from .celery_app import celery_app
from . import ml_service, models
from .database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def analyze_image_task(self, task_id: str, file_path: str):
    """
    Анализирует загруженное изображение пищи и возвращает состав КБЖУ
    """
    session = SessionLocal()
    task = None

    try:
        logger.info(f"Starting image analysis for task {task_id} and file {file_path}")
        task = session.query(models.Task).filter(models.Task.id == task_id).first()
        if task:
            task.status = models.TaskStatus.PROCESSING
            task.updated_at = datetime.utcnow()
            session.commit()

        result = ml_service.analyze_image_sync(file_path)
        logger.info(f"Analysis completed for {file_path}: {result.get('food') if isinstance(result, dict) else 'unknown'}")

        if task:
            task.status = models.TaskStatus.SUCCESS
            task.result_json = json.dumps(result, ensure_ascii=False)
            task.error = None
            task.updated_at = datetime.utcnow()
            session.commit()

        return result

    except Exception as e:
        logger.exception(f"Image analysis failed for task {task_id}: {e}")
        if task:
            task.status = models.TaskStatus.FAILURE
            task.error = str(e)
            task.updated_at = datetime.utcnow()
            session.commit()
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 600))
    finally:
        session.close()


@celery_app.task(bind=True, max_retries=1)
def retrain_model_task(self):
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