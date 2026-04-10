# app/database.py
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
from .config import settings
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

# ----------------- Асинхронный движок -----------------
# Поддерживает PostgreSQL (asyncpg) и SQLite (aiosqlite)
if "postgresql" in settings.DATABASE_URL:
    async_db_url = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
elif "sqlite" in settings.DATABASE_URL:
    async_db_url = settings.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
else:
    async_db_url = settings.DATABASE_URL

async_engine = create_async_engine(
    async_db_url,
    echo=False,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

AsyncSessionLocal = sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False
)

async def get_db() -> AsyncSession:
    """Асинхронная зависимость для FastAPI."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

# ----------------- Синхронный движок -----------------
if "postgresql" in settings.DATABASE_URL:
    sync_db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
elif "sqlite" in settings.DATABASE_URL:
    sync_db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")
else:
    sync_db_url = settings.DATABASE_URL

# Для SQLite нужен дополнительный аргумент
if "sqlite" in sync_db_url:
    sync_engine = create_engine(
        sync_db_url,
        echo=False,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
else:
    sync_engine = create_engine(
        sync_db_url,
        echo=False,
        pool_pre_ping=True,
    )

# Алиас для совместимости с существующим кодом (main.py импортирует engine)
engine = sync_engine

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_sync_db():
    """Синхронная зависимость для FastAPI."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------- Инициализация -----------------
async def init_db():
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database initialized")

async def close_db():
    await async_engine.dispose()
    sync_engine.dispose()
    logger.info("Database connections closed")