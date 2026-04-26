# app/database.py
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy import create_engine
from .config import settings
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

# Синхронный движок (основной)
engine = create_engine(
    settings.DATABASE_URL,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def get_db():
    """Синхронная зависимость для FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Инициализация БД (создание всех таблиц)."""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


def close_db():
    """Закрытие соединений с БД."""
    engine.dispose()
    logger.info("Database connections closed")