from pydantic_settings import BaseSettings
from typing import Optional, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ===================== CORE =====================

    DATABASE_URL: str = "postgresql+asyncpg://fooduser:foodpass@postgres:5432/fooddb"

    REDIS_URL: str = "redis://redis:6379/0"

    # 🔥 MODEL CONFIG
    MODEL_PROVIDER: str = "gemini"
    GEMINI_MODEL: str = "gemini-2.5-flash-image"

    # 👉 подтягивается из .env
    GEMINI_API_KEY: str

    # 🔥 оптимально под API
    MODEL_TIMEOUT_SECONDS: int = 10
    MODEL_RETRY_ATTEMPTS: int = 2
    MODEL_BACKOFF_FACTOR: float = 1.0

    # ===================== SECURITY =====================

    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ===================== FILES =====================

    UPLOAD_DIR: str = "/app/app/uploads"

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # 🔥 уменьшили для экономии токенов
    MAX_IMAGE_SIZE: int = 512
    IMAGE_QUALITY: int = 85

    ALLOWED_EXTENSIONS: Set[str] = {
        ".jpg", ".jpeg", ".png", ".webp"
    }

    # ===================== CACHE =====================

    CACHE_TTL: int = 60 * 60 * 24
    CACHE_PREFIX: str = "food_analysis:v2"  # 🔥 версия кэша

    # ===================== CELERY =====================

    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    # ===================== DERIVED =====================

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

    # ===================== VALIDATION =====================

    def model_post_init(self, __context):
        if not self.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is not set in environment variables")

        if self.MODEL_PROVIDER != "gemini":
            logger.warning("MODEL_PROVIDER is not 'gemini' — current setup expects Gemini")

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = True


settings = Settings()