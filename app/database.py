# app/database.py
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy import create_engine
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


def close_db():
    """Закрытие соединений с БД."""
    engine.dispose()
    logger.info("Database connections closed")