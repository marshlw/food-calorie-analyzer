from pydantic_settings import BaseSettings
from typing import Optional, Set
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # ===================== CORE =====================

    DATABASE_URL: str = "postgresql://fooduser:foodpass@postgres:5432/fooddb"

    # Пул соединений с БД на ПРОЦЕСС (uvicorn-воркер / celery-процесс).
    # Итоговый максимум коннектов = (кол-во процессов) * (POOL_SIZE + MAX_OVERFLOW).
    # Текущий бюджет при max_connections=150:
    #   api    2 процесса uvicorn * (5 + 5) = 20
    #   celery 1 процесс (пул потоков)      = 10 на 8 задач
    #   beat   1 процесс                    = ~1
    # Запас оставлен под psql/бэкапы и рост числа воркеров.
    # Под 5000 DAU правильное решение — PgBouncer в режиме transaction.
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 5

    # Redis хранит очередь Celery, кэш анализа, счётчики rate-limit и учёт
    # активных refresh-токенов — то есть компрометация Redis = обход лимитов
    # и брутфорс-защиты. Пароль обязателен в проде (M-3): сетевая изоляция
    # одна не спасает, любая ошибка в конфигурации сети всё это открывает.
    # Формат с паролем: redis://:ПАРОЛЬ@redis:6379/0
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

    # В prod поставь ENABLE_DOCS=false в .env — /docs, /redoc и /openapi.json
    # не будут раскрывать поверхность API (включая админ-эндпоинты)
    ENABLE_DOCS: bool = False

    SECRET_KEY: str = "change-this-in-production"
    # Разрешить запуск с плейсхолдером в SECRET_KEY. ТОЛЬКО для локальной
    # разработки/тестов: в проде приложение с дефолтным ключом не стартует.
    ALLOW_INSECURE_SECRET_KEY: bool = False

    # Разрешить запуск со слабым паролем БД в DATABASE_URL (foodpass/adminpass/...).
    # ТОЛЬКО для локальной разработки/тестов: в проде с таким паролем приложение
    # не стартует (по аналогии с ALLOW_INSECURE_SECRET_KEY). В .env.dev/.env.test
    # ставим true, в прод-.env — не задаём.
    ALLOW_INSECURE_DB_PASSWORD: bool = False
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Доп. доверенные прокси (запятая-разделитель) для X-Forwarded-For.
    # Приватные/loopback адреса доверяются автоматически (nginx в docker-сети).
    TRUSTED_PROXIES: str = ""

    # ===================== RATE LIMITING =====================

    RATE_LIMIT_ENABLED: bool = True

    # Брутфорс: попытки login/token с одного IP за окно
    AUTH_RATE_LIMIT_ATTEMPTS: int = 10
    AUTH_RATE_LIMIT_WINDOW: int = 60  # секунд

    # Брутфорс: неудачные попытки входа по одному email
    AUTH_FAILED_ATTEMPTS_LIMIT: int = 5
    AUTH_FAILED_ATTEMPTS_WINDOW: int = 900  # 15 минут

    # Регистрации с одного IP
    REGISTER_RATE_LIMIT_ATTEMPTS: int = 5
    REGISTER_RATE_LIMIT_WINDOW: int = 3600  # 1 час

    # AI-анализ фото: запросов в сутки на одного пользователя
    AI_DAILY_LIMIT: int = 5

    # Советчик: сколько раз в сутки один пользователь может инициировать
    # LLM-вызов через GET /advisor. Без лимита любое изменение дневника
    # инвалидирует кэш совета, и открытие вкладки = новый платный вызов
    # на десятки секунд.
    ADVISOR_DAILY_LIMIT: int = 20

    # ===================== НАБЛЮДАЕМОСТЬ =====================

    # Эндпоинт /metrics в формате Prometheus. Наружу не публикуется:
    # Caddy отвечает на /metrics 404, доступ только изнутри сети backend.
    METRICS_ENABLED: bool = True

    # ===================== RETRAIN =====================

    # Ретрейн модели по фидбекам. В прод-образе нет ollama, поэтому по
    # умолчанию выключено: иначе каждый фидбек после десятого ставил в
    # очередь заведомо падающую задачу. См. tasks.retrain_model_task.
    RETRAIN_ENABLED: bool = False

    # ===================== FILES =====================

    UPLOAD_DIR: str = "/app/app/uploads"

    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10 MB

    # Срок жизни подписанной ссылки на фото (/uploads/... с HMAC-подписью)
    UPLOAD_URL_TTL: int = 24 * 3600

    # Удалять оригинал фото после успешного анализа (превью перестанет работать)
    DELETE_UPLOAD_AFTER_ANALYSIS: bool = False

    # Сколько дней держать фото в UPLOAD_DIR. Ночная задача
    # tasks.cleanup_uploads_task удаляет всё старше этого срока, а также
    # «осиротевшие» файлы, на которые не ссылается ни одна строка в БД.
    # Записи КБЖУ при этом остаются — исчезает только картинка.
    # Оценка роста: 5000 DAU * 1,5 фото * ~400 КБ ≈ 3 ГБ/сутки,
    # то есть 30 дней ≈ 90 ГБ. Уменьшайте, если диск меньше.
    UPLOAD_RETENTION_DAYS: int = 30

    # Порог свободного места на томе uploads. Ниже — задача уборки пишет
    # ERROR (повод для алерта), потому что при 0 байт падает и Postgres.
    UPLOAD_DISK_FREE_ALERT_GB: float = 5.0

    # Увеличили для лучшего распознавания
    MAX_IMAGE_SIZE: int = 1600
    IMAGE_QUALITY: int = 95

    # Потолок разрешения входного фото (защита от decompression bomb:
    # 10 МБ PNG могут развернуться в сотни МБ RSS при декодировании).
    # Считаем бюджет памяти воркера: N пикселей * 3 байта на RGB, и ещё
    # столько же на копию при convert("RGB") в preprocess.
    #   30 Мп -> ~90 МБ + копия = ~180 МБ на одно фото.
    # Одновременно декодируется максимум пара картинок из 8 задач воркера
    # (остальные ждут ответ сети), но поднимать порог без увеличения RAM
    # нельзя: прилетит OOM-killer, а задачи с acks_late=True вернутся в
    # очередь и зациклятся.
    # 30 Мп покрывает любую телефонную камеру (48 Мп режимы дают файл
    # заметно больше MAX_UPLOAD_SIZE и отсекаются раньше).
    MAX_IMAGE_PIXELS: int = 30_000_000

    # .heic/.heif — камера iPhone. Safari транскодирует их в JPEG не всегда
    # (при выборе через «Файлы» и во встроенных WebView — нет), поэтому
    # принимаем как есть и нормализуем на сервере.
    ALLOWED_EXTENSIONS: Set[str] = {
        ".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif"
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

    # ===================== ADVISOR =====================

    # Сколько LLM-вызовов советчика может идти одновременно (свой пул потоков,
    # чтобы не занимать общий threadpool FastAPI и не подвешивать API).
    ADVISOR_MAX_CONCURRENCY: int = 8

    # ===================== CACHE =====================

    CACHE_TTL: int = 60 * 60 * 24
    CACHE_PREFIX: str = "food_analysis:v4"   # ← подняли версию кэша

    # ===================== CELERY =====================

    # Пустые по умолчанию: подставляются из REDIS_URL в model_post_init.
    # Так пароль Redis задаётся ровно в одном месте и нельзя получить
    # «половинчатую» конфигурацию, где API ходит с паролем, а Celery — без
    # него и молча падает с NOAUTH (M-3).
    # Задавайте явно, только если брокер живёт отдельно от кэша.
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

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
        # Celery по умолчанию ходит туда же, куда и кэш — вместе с паролем
        if not self.CELERY_BROKER_URL:
            self.CELERY_BROKER_URL = self.REDIS_URL
        if not self.CELERY_RESULT_BACKEND:
            self.CELERY_RESULT_BACKEND = self.REDIS_URL

        # Домены из env добавляем к дефолтному списку (прод-домен, мобилка)
        extra = [o.strip() for o in self.ALLOWED_ORIGINS_EXTRA.split(",") if o.strip()]
        for origin in extra:
            if origin not in self.ALLOWED_ORIGINS:
                self.ALLOWED_ORIGINS.append(origin)

        # Не даём молча уехать в prod с дефолтным/коротким SECRET_KEY:
        # им подписываются JWT — зная его, можно выпустить токен любого юзера.
        # Ловим и типовые «человеческие» заглушки, а не только дефолт.
        _placeholder_markers = (
            "change-this", "changeme", "change-me", "your-super-secret",
            "secret-key", "example", "placeholder", "12345",
        )
        key_lower = self.SECRET_KEY.lower()
        if any(m in key_lower for m in _placeholder_markers):
            message = (
                "SECRET_KEY looks like a placeholder! Generate a strong value: "
                "python3 -c \"import secrets; print(secrets.token_urlsafe(48))\" "
                "and set it in .env before deploying."
            )
            if not self.ALLOW_INSECURE_SECRET_KEY:
                # Зная ключ, можно выпустить JWT любого пользователя —
                # с дефолтным ключом приложение подниматься не должно.
                raise RuntimeError(message)
            logger.critical("%s (ALLOW_INSECURE_SECRET_KEY=true — запуск разрешён)", message)
        elif len(self.SECRET_KEY) < 32:
            logger.warning(
                "SECRET_KEY is shorter than 32 chars — consider a longer random value."
            )

        # Не даём молча уехать в prod со слабым паролем БД. Порт наружу не
        # публикуется, но пароль по словарю — вторая линия обороны при любой
        # ошибке в сети/файрволе. Список — типовые заглушки из этого проекта.
        _weak_db_passwords = {
            "foodpass", "adminpass", "postgres", "password", "devpass",
            "testpass", "changeme", "admin", "",
        }
        try:
            db_password = urlparse(self.DATABASE_URL).password
        except Exception:
            db_password = None
        # None => пароль в URL не задан (например, sqlite в тестах) — не проверяем.
        if db_password is not None and db_password.lower() in _weak_db_passwords:
            message = (
                "DATABASE_URL uses a weak/default password! Generate a strong value: "
                "python3 -c \"import secrets; print(secrets.token_urlsafe(32))\" "
                "and set it in .env (APP_DB_PASSWORD + DATABASE_URL) before deploying."
            )
            if not self.ALLOW_INSECURE_DB_PASSWORD:
                raise RuntimeError(message)
            logger.critical("%s (ALLOW_INSECURE_DB_PASSWORD=true — запуск разрешён)", message)

        # M-3: Redis без пароля. В нём лежат очередь Celery, счётчики
        # rate-limit и учёт активных refresh-токенов — доступ к нему
        # позволяет обойти брутфорс-защиту и дневные лимиты.
        # Предупреждение, а не отказ старта: в dev/тестах Redis поднимают
        # без пароля, и ронять из-за этого приложение неправильно.
        try:
            redis_password = urlparse(self.REDIS_URL).password
        except Exception:
            redis_password = None
        if not redis_password:
            logger.warning(
                "REDIS_URL has no password. In production run redis with "
                "--requirepass and use redis://:PASSWORD@redis:6379/0 — "
                "network isolation alone is not enough."
            )

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