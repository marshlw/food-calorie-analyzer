from pathlib import Path
import logging
import subprocess
import sys
import uuid

from .celery_app import celery_app
from . import ml_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def analyze_image_task(self, file_path: str):
    """
    Анализирует загруженное изображение пищи и возвращает состав КБЖУ
    """
    try:
        logger.info(f"Starting image analysis for: {file_path}")
        
        # Анализируем изображение
        result = ml_service.analyze_image_sync(file_path)
        
        logger.info(f"Analysis completed for {file_path}: {result.get('food')}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Image analysis failed: {e}")
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=e, countdown=min(2 ** self.request.retries, 600))


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