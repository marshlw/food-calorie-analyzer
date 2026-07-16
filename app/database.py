# app/database.py
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
    # Пул на ПРОЦЕСС: 2 uvicorn-воркера + 4 celery-процесса = 6 пулов.
    # При 20+10 на процесс под нагрузкой это до 180 коннектов — больше
    # дефолтного max_connections=100 у Postgres. 5+5 на процесс (до 60)
    # безопасно и с запасом покрывает ~10-50 активных пользователей.
    engine = create_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=5,
        pool_recycle=1800,
        pool_pre_ping=True,
    )
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )
    logger.info("Database configured for %s", database_url)


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
    # Ручные нормы КБЖУ/воды (NULL = авторасчёт)
    "custom_calorie_target": "FLOAT",
    "custom_protein_g": "FLOAT",
    # Ручное разделение нормы белка на животный/растительный
    "custom_protein_animal_g": "FLOAT",
    "custom_protein_plant_g": "FLOAT",
    "custom_fat_g": "FLOAT",
    "custom_carbs_g": "FLOAT",
    "custom_water_ml": "FLOAT",
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
    # Разделение белка в «старой» модели приёмов
    "meals": {
        "total_protein_animal": "FLOAT",
        "total_protein_plant": "FLOAT",
    },
    "meal_items": dict(_PROTEIN_SPLIT_COLUMNS),
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
    ("ix_meals_user_id", "meals", "user_id"),
    ("ix_daily_logs_user_id", "daily_logs", "user_id"),
)


def ensure_schema():
    """Лёгкая «миграция» для проектов без Alembic.

    create_all() создаёт недостающие ТАБЛИЦЫ (например, weight_records),
    но не добавляет новые КОЛОНКИ и ИНДЕКСЫ в существующие таблицы.
    Здесь идемпотентно дольём недостающие колонки users и индексы.
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