# app/database.py
from urllib.parse import urlparse

from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy import create_engine, inspect, text
from .config import settings
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()
engine = None
SessionLocal = None


def configure_database(url: str | None = None):
    """Configure the database engine and session factory."""
    global engine, SessionLocal
    database_url = url or settings.DATABASE_URL
    # Пул на ПРОЦЕСС, размер задаётся в .env (DB_POOL_SIZE / DB_MAX_OVERFLOW).
    # Итоговый максимум коннектов = процессы * (pool_size + max_overflow):
    # следите, чтобы он не превышал max_connections Postgres (или используйте
    # PgBouncer). Дефолт 10+20 рассчитан на сотни одновременных пользователей.
    engine = create_engine(
        database_url,
        echo=False,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=1800,
        pool_pre_ping=True,
        # Пул меньше, чем threadpool FastAPI, поэтому под пиком запросы будут
        # ждать соединение. Ждать 30 с (дефолт) бессмысленно: клиент уже
        # отвалился по таймауту. Падаем быстро — запрос вернёт 500, но воркер
        # не будет держать зависшие потоки.
        pool_timeout=10,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    # Пароль в лог не пишем: строка подключения содержит его открытым текстом,
    # а логи живут дольше секрета и часто уезжают в агрегатор.
    try:
        parsed = urlparse(database_url)
        safe_target = f"{parsed.hostname or '?'}:{parsed.port or '?'}{parsed.path or ''}"
    except Exception:
        safe_target = "unknown"
    logger.info("Database configured for %s", safe_target)


configure_database()


def get_db():
    """Синхронная зависимость для FastAPI."""
    if SessionLocal is None:
        raise RuntimeError("Database has not been configured")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация БД (создание всех таблиц)."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


# Колонки, которые могли появиться после первого create_all() и которые
# create_all НЕ добавляет в уже существующую таблицу. Тип задаём в виде
# SQL, совместимом и с SQLite, и с PostgreSQL.
_PROFILE_COLUMNS = {
    "height_cm": "FLOAT",
    "sex": "VARCHAR",
    "birth_date": "DATE",
    "activity_level": "VARCHAR",
    # Цель по весу: lose|maintain|gain + желаемый темп и целевой вес.
    # NULL = поддержание с дефолтным темпом (см. app/nutrition.py).
    "goal": "VARCHAR",
    "goal_rate_kg_per_week": "FLOAT",
    "target_weight_kg": "FLOAT",
    # Ручные нормы КБЖУ/воды (NULL = авторасчёт)
    "custom_calorie_target": "FLOAT",
    "custom_protein_g": "FLOAT",
    # Ручное разделение нормы белка на животный/растительный
    "custom_protein_animal_g": "FLOAT",
    "custom_protein_plant_g": "FLOAT",
    "custom_fat_g": "FLOAT",
    "custom_carbs_g": "FLOAT",
    "custom_water_ml": "FLOAT",
    # Версия токенов: инкремент инвалидирует все выданные JWT пользователя
    # (смена пароля, компрометация). См. auth.get_current_user.
    "token_version": "INTEGER DEFAULT 0",
    # Геймификация («Цели» / вкладка «Путь»): запас заморозок серии, рекорд
    # серии и коды уже выданных наград. См. app/goals.py.
    "goal_freezes_available": "INTEGER DEFAULT 2",
    "goal_best_streak": "INTEGER DEFAULT 0",
    "goal_rewards_granted": "VARCHAR",
}

# Разделение белка на животный/растительный (появилось после первого create_all).
_PROTEIN_SPLIT_COLUMNS = {
    "protein_animal_g": "FLOAT",
    "protein_plant_g": "FLOAT",
}

# Обхваты тела на записи взвешивания (появились после первого create_all).
_WEIGHT_RECORD_COLUMNS = {
    "waist_cm": "FLOAT",
    "chest_cm": "FLOAT",
    "hips_cm": "FLOAT",
    "shoulders_cm": "FLOAT",
}

# Недостающие колонки по таблицам (та же логика, что для users).
_ENSURE_COLUMNS = {
    "users": _PROFILE_COLUMNS,
    # Фото + разделение белка на записи приёма пищи
    "meal_entries": {"photo_path": "VARCHAR", **_PROTEIN_SPLIT_COLUMNS},
    # Разделение белка на блюдах составного приёма
    "meal_entry_items": dict(_PROTEIN_SPLIT_COLUMNS),
    # Тег источника белка продукта (animal|plant|mixed)
    "products": {"protein_type": "VARCHAR"},
    # Обхваты тела в истории замеров
    "weight_records": _WEIGHT_RECORD_COLUMNS,
}


# Индексы для «старых» таблиц, созданных до того, как в моделях появились
# index=True: create_all не добавляет индексы в существующие таблицы.
# FK без индекса = seq scan на каждый запрос дневника/истории.
_ENSURE_INDEXES = (
    ("ix_meal_entries_daily_log_id", "meal_entries", "daily_log_id"),
    ("ix_tasks_user_id", "tasks", "user_id"),
    ("ix_daily_logs_user_id", "daily_logs", "user_id"),
    ("ix_goal_days_user_id", "goal_days", "user_id"),
    ("ix_goal_days_date", "goal_days", "date"),
    # create_feedback_sync считает COUNT(*) WHERE status='pending' на КАЖДОМ
    # фидбеке — без индекса это seq scan по всей таблице (M-11)
    ("ix_feedback_status", "feedback", "status"),
)


# Триграммные индексы для автодополнения (M-1).
# Поиск идёт как ilike '%слово%': ведущий wildcard делает B-tree индекс
# бесполезным, и Postgres уходит в seq scan по products/exercises на КАЖДОЕ
# нажатие клавиши — это самый частый запрос в приложении.
# GIN + pg_trgm умеет обслуживать подстроку в середине строки.
# Работает только в PostgreSQL; в SQLite (тесты) молча пропускается.
_TRGM_INDEXES = (
    ("ix_products_name_trgm", "products", "name"),
    ("ix_exercises_name_trgm", "exercises", "name"),
)


def _ensure_trgm_indexes(tables: set) -> None:
    """Идемпотентно создаёт pg_trgm-индексы.

    КАЖДЫЙ оператор — в СВОЕЙ транзакции: в Postgres первая же ошибка
    переводит транзакцию в aborted, и все последующие команды в ней падают
    с "current transaction is aborted". Один неудавшийся индекс не должен
    утаскивать за собой остальные.

    Любая ошибка (нет прав на CREATE EXTENSION, старая версия Postgres) —
    предупреждение, а не падение старта: приложение работает и без
    индексов, просто медленнее. Основной путь установки расширения —
    init.sh, там мы суперпользователь.
    """
    statements = [("pg_trgm extension", "CREATE EXTENSION IF NOT EXISTS pg_trgm")]
    for index_name, table, column in _TRGM_INDEXES:
        if table not in tables:
            continue
        # ВАЖНО: индекс по САМОЙ колонке, без lower(). Запросы идут через
        # ILIKE (crud.search_products / search_exercises), а gin_trgm_ops
        # по колонке обслуживает и LIKE, и ILIKE. Индекс по lower(column)
        # планировщик для ILIKE не подхватит — понадобилось бы переписать
        # запросы на lower(name) LIKE lower(...).
        statements.append((index_name, (
            f"CREATE INDEX IF NOT EXISTS {index_name} "
            f"ON {table} USING gin ({column} gin_trgm_ops)"
        )))

    for label, sql in statements:
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
        except Exception as exc:
            logger.warning("Skipping %s: %s", label, exc)
            if label == "pg_trgm extension":
                return  # без расширения индексы всё равно не создадутся


def ensure_schema():
    """Схема одним вызовом: create_all + недостающие колонки и индексы.

    ТОЛЬКО ДЛЯ DEV И ТЕСТОВ. В проде схему накатывает Alembic
    (`alembic upgrade head` в сервисе `migrate`, миграция 0004_schema_baseline
    выполняет ровно эти же шаги). Вызывать это из startup-хука НЕЛЬЗЯ:
    воркеры стартуют одновременно и устраивают гонку на DDL, ADD COLUMN
    берёт ACCESS EXCLUSIVE lock, а CREATE INDEX без CONCURRENTLY блокирует
    запись в таблицу — и всё это на каждом деплое (H-7).

    create_all() создаёт недостающие ТАБЛИЦЫ (например, weight_records),
    но не добавляет новые КОЛОНКИ и ИНДЕКСЫ в существующие таблицы.
    """
    if engine is None:
        raise RuntimeError("Database has not been configured")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    # Недостающие индексы (идемпотентно)
    with engine.begin() as conn:
        for index_name, table, column in _ENSURE_INDEXES:
            if table in tables:
                conn.execute(text(
                    f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})'
                ))

    if engine.dialect.name == "postgresql":
        _ensure_trgm_indexes(tables)

    for table, columns in _ENSURE_COLUMNS.items():
        if table not in tables:
            continue
        existing = {col["name"] for col in inspector.get_columns(table)}
        missing = {k: v for k, v in columns.items() if k not in existing}
        if not missing:
            continue
        with engine.begin() as conn:
            for name, sql_type in missing.items():
                conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}'))
                logger.info("Added missing column %s.%s (%s)", table, name, sql_type)


def close_db():
    """Закрытие соединений с БД."""
    engine.dispose()
    logger.info("Database connections closed")