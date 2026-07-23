"""Alembic runtime environment.

URL БД и метаданные берём из самого приложения, чтобы:
  * не дублировать секрет подключения в alembic.ini (он приходит из .env/секретов);
  * autogenerate видел актуальные модели (Base.metadata) без ручной синхронизации.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# --- Приложение: настройки и метаданные моделей -----------------------------
# env.py запускается из корня проекта (prepend_sys_path = . в alembic.ini),
# поэтому пакет app импортируется напрямую.
from app.config import settings
from app.database import Base
from app import models  # noqa: F401  — регистрирует все таблицы в Base.metadata

config = context.config

# Подставляем реальный URL из настроек приложения (единый источник правды).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Генерация SQL без подключения к БД (`alembic upgrade --sql`)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Применение миграций через живое соединение."""
    section = config.get_section(config.config_ini_section, {})
    connectable = engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
