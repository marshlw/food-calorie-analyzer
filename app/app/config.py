from pydantic_settings import BaseSettings
from typing import Set
import logging
logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://fooduser:foodpass@postgres:5432/fooddb"
    REDIS_URL: str = "redis://redis:6379/0"
    OLLAMA_HOST: str = "http://ollama:11434"
    MODEL_NAME: str = "llava"
    SECRET_KEY: str = "your-secret-key-here-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    UPLOAD_DIR: str = "/app/app/uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB
    MAX_IMAGE_SIZE: int = 1024
    IMAGE_QUALITY: int = 85
    ALLOWED_EXTENSIONS: Set[str] = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    CACHE_TTL: int = 3600
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()