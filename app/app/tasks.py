from pathlib import Path
import logging

from .celery_app import celery_app
from . import ml_service

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def analyze_image_task(self, image_path: str):
    path = Path(image_path)

    try:
        logger.info(f"Starting analysis for {image_path}")

        # 🔥 важно: sync-only функция
        result = ml_service.analyze_image_sync(image_path)

        logger.info(f"Analysis completed for {image_path}")
        return result

    except Exception as e:
        logger.exception(f"Error analyzing {image_path}: {e}")
        raise self.retry(exc=e, countdown=60)

    finally:
        # безопасное удаление файла
        try:
            if path.exists():
                path.unlink()
        except Exception as unlink_error:
            logger.warning(f"Could not delete {image_path}: {unlink_error}")