"""schema baseline: переносит ad-hoc DDL из startup-хука в миграции (H-7)

До этой миграции схема добиралась на старте КАЖДОГО процесса api/celery:
create_all() + ALTER TABLE ADD COLUMN + CREATE INDEX. Проблемы были такие:

  * два uvicorn-воркера стартуют одновременно -> гонка на DDL;
  * ADD COLUMN на живой таблице берёт ACCESS EXCLUSIVE lock;
  * CREATE INDEX без CONCURRENTLY блокирует запись в таблицу;
  * всё это выполнялось при каждом деплое и каждом рестарте контейнера.

Теперь тот же набор применяется ОДИН раз отдельным шагом деплоя
(сервис `migrate` в docker-compose.prod.yml), а startup-хук приложения
занимается только прогревом HTTP/Redis клиентов.

Миграция полностью ИДЕМПОТЕНТНА и рассчитана на два сценария:
  1. чистая БД — create_all создаёт все таблицы;
  2. существующая прод-база, никогда не помеченная alembic — таблицы уже
     есть, доливаются только недостающие колонки и индексы.

ОГОВОРКА: здесь намеренно используется Base.metadata (живые модели), а не
замороженный снимок схемы. Это осознанный компромисс: проект вырос на
create_all, и повторять всю схему руками означало бы получить второй
источник правды, который разъедется с моделями. Все ПОСЛЕДУЮЩИЕ изменения
схемы должны оформляться обычными миграциями с явными op.add_column().

Revision ID: 0004_schema_baseline
Revises: 0003_goals
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_schema_baseline"
down_revision: Union[str, None] = "0003_goals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Импорт внутри функции: alembic-окружение уже добавило корень проекта
    # в sys.path, а на уровне модуля это ломало бы `alembic history` без .env
    from app.database import (
        Base,
        _ENSURE_COLUMNS,
        _ENSURE_INDEXES,
        _TRGM_INDEXES,
    )
    from app import models  # noqa: F401 — регистрирует таблицы в Base.metadata

    bind = op.get_bind()

    # ---- 1. Недостающие ТАБЛИЦЫ ----
    # checkfirst=True по умолчанию: существующие таблицы не трогаются
    Base.metadata.create_all(bind=bind)

    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    # ---- 2. Недостающие КОЛОНКИ ----
    # create_all не добавляет колонки в уже существующие таблицы
    for table, columns in _ENSURE_COLUMNS.items():
        if table not in tables:
            continue
        existing = {c["name"] for c in inspector.get_columns(table)}
        for name, sql_type in columns.items():
            if name not in existing:
                op.execute(f'ALTER TABLE {table} ADD COLUMN {name} {sql_type}')

    # ---- 3. Недостающие ИНДЕКСЫ ----
    for index_name, table, column in _ENSURE_INDEXES:
        if table in tables:
            op.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({column})')

    # ---- 4. Триграммные индексы автодополнения (M-1) ----
    # Поиск идёт через ILIKE '%слово%' — B-tree бесполезен, нужен GIN+pg_trgm.
    # Расширение обычно уже стоит (init.sh), здесь страховка для баз,
    # поднятых до появления init.sh.
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        for index_name, table, column in _TRGM_INDEXES:
            if table in tables:
                op.execute(
                    f"CREATE INDEX IF NOT EXISTS {index_name} "
                    f"ON {table} USING gin ({column} gin_trgm_ops)"
                )


def downgrade() -> None:
    # Откат бессмысленен: это baseline существующей схемы. Дропать таблицы
    # с пользовательскими данными миграция не должна.
    pass
