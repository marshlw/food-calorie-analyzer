from pydantic_settings import BaseSettings
from typing import Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ===================== CORE =====================

    DATABASE_URL: str = "postgresql+asyncpg://fooduser:foodpass@postgres:5432/fooddb"

    REDIS_URL: str = "redis://redis:6379/0"

    OLLAMA_HOST: str = "http://ollama:11434"
    MODEL_NAME: str = "llava:7b"

    SECRET_KEY: str = "your-secret-key-here-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ===================== FILES =====================

    UPLOAD_DIR: str = "/app/app/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    MAX_IMAGE_SIZE: int = 1024
    IMAGE_QUALITY: int = 85

    ALLOWED_EXTENSIONS: Set[str] = {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"
    }

    # ===================== CACHE =====================

    CACHE_TTL: int = 60 * 60 * 24  # 🔥 24 часа (лучше для изображений)
    CACHE_PREFIX: str = "food_analysis:v1"

    # ===================== CELERY =====================

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # ===================== DERIVED (AUTO) =====================

    @property
    def REDIS_HOST(self) -> str:
        try:
            return urlparse(self.REDIS_URL).hostname or "redis"
        except Exception:
            return "redis"

    @property
    def REDIS_PORT(self) -> int:
        try:
            return urlparse(self.REDIS_URL).port or 6379
        except Exception:
            return 6379

    @property
    def REDIS_DB(self) -> int:
        try:
            path = urlparse(self.REDIS_URL).path
            return int(path.replace("/", "")) if path else 0
        except Exception:
            return 0

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()