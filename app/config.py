from pydantic_settings import BaseSettings
from typing import Optional, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ===================== CORE =====================

    DATABASE_URL: str = "postgresql://fooduser:foodpass@postgres:5432/fooddb"

    REDIS_URL: str = "redis://redis:6379/0"
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_VISION_API_URL: Optional[str] = None
    DEEPSEEK_VISION_MODEL: str = "gpt-image-1"
    # 🔥 MODEL CONFIG
    MODEL_PROVIDER: str = "yandex"
    GEMINI_MODEL: str = "gemini-2.5-flash-image"
    OLLAMA_HOST: str = "http://ollama:11434"
    OLLAMA_MODEL: str = "llava:7b"

    # Yandex settings
    YANDEX_API_KEY: Optional[str] = None
    YANDEX_FOLDER_ID: Optional[str] = None
    YANDEX_VISION_MODEL: str = "qwen3.6-35b-a3b/latest"
    YANDEX_API_URL: str = "https://ai.api.cloud.yandex.net/v1"
    # Глубина рассуждений модели: none|low|medium|high.
    # low — баланс скорости и точности; medium точнее, но медленнее и может
    # упираться в лимит токенов на многосоставных блюдах.
    YANDEX_REASONING_EFFORT: str = "low"
    # Бюджет выходных токенов (рассуждения + JSON). С reasoning часть уходит
    # на «мысли», поэтому запас, иначе ответ обрывается до JSON.
    YANDEX_MAX_OUTPUT_TOKENS: int = 4000
    # 👉 подтягивается из .env
    GEMINI_API_KEY: Optional[str] = None

    # 🔥 оптимально под API
    MODEL_TIMEOUT_SECONDS: int = 45
    MODEL_RETRY_ATTEMPTS: int = 2
    MODEL_BACKOFF_FACTOR: float = 1.0
    MODEL_COOLDOWN_SECONDS: int = 300

    # ===================== SECURITY =====================

    SECRET_KEY: str = "change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ===================== FILES =====================

    UPLOAD_DIR: str = "/app/app/uploads"

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # Увеличили для лучшего распознавания
    MAX_IMAGE_SIZE: int = 1600
    IMAGE_QUALITY: int = 95

    ALLOWED_EXTENSIONS: Set[str] = {
        ".jpg", ".jpeg", ".png", ".webp"
    }

    # ===================== CORS =====================

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:8000",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:8000",
        "http://0.0.0.0:8000",
    ]

    # Доп. origins через env (запятая-разделитель): прод-домен, capacitor://localhost и т.п.
    # Пример: ALLOWED_ORIGINS_EXTRA="https://myapp.ru,capacitor://localhost"
    ALLOWED_ORIGINS_EXTRA: str = ""

    # ===================== CACHE =====================

    CACHE_TTL: int = 60 * 60 * 24
    CACHE_PREFIX: str = "food_analysis:v4"   # ← подняли версию кэша

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
        # Домены из env добавляем к дефолтному списку (прод-домен, мобилка)
        extra = [o.strip() for o in self.ALLOWED_ORIGINS_EXTRA.split(",") if o.strip()]
        for origin in extra:
            if origin not in self.ALLOWED_ORIGINS:
                self.ALLOWED_ORIGINS.append(origin)

        providers = {"gemini", "deepseek", "ollama", "yandex"}
        if self.MODEL_PROVIDER not in providers:
            logger.warning(
                "MODEL_PROVIDER is not one of %s — current setup may not use the expected provider",
                ", ".join(sorted(providers)),
            )

    class Config:
        env_file = ".env"
        extra = "ignore"
        case_sensitive = True


settings = Settings()