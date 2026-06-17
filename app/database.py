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
    engine = create_engine(
        database_url,
        echo=False,
        pool_size=20,
        max_overflow=10,
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
}


def ensure_schema():
    """Лёгкая «миграция» для проектов без Alembic.

    create_all() создаёт недостающие ТАБЛИЦЫ (например, weight_records),
    но не добавляет новые КОЛОНКИ в существующие таблицы. Здесь мы
    идемпотентно дольём недостающие колонки профиля в users.
    """
    if engine is None:
        raise RuntimeError("Database has not been configured")

    Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("users")}
    missing = {k: v for k, v in _PROFILE_COLUMNS.items() if k not in existing}
    if not missing:
        return

    with engine.begin() as conn:
        for name, sql_type in missing.items():
            conn.execute(text(f'ALTER TABLE users ADD COLUMN {name} {sql_type}'))
            logger.info("Added missing column users.%s (%s)", name, sql_type)


def close_db():
    """Закрытие соединений с БД."""
    engine.dispose()
    logger.info("Database connections closed")