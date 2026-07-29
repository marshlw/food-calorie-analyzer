"""add goals gamification: goal_days table + user freeze/streak columns

«Цели» — вкладка «Приёмы» → «Путь»: цель дня, серия, путь месяца, награды
и заморозки (см. app/goals.py).

goal_days хранит СНИМОК дня (закрыт/частично/заморозка/пропуск + искры).
Без снимка смена норм в профиле переписывала бы историю задним числом,
а статус «заморозка» вообще не выводится из данных — это явное действие
пользователя.

Колонки users добавляются с server_default, чтобы существующие строки
получили корректные значения (2 заморозки, рекорд 0) без отдельного UPDATE.

Revision ID: 0003_goals
Revises: 0002_user_goal
Create Date: 2026-07-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_goals"
down_revision: Union[str, None] = "0002_user_goal"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Имя -> (тип, server_default). Тот же набор, что и в database._PROFILE_COLUMNS:
# проекты без Alembic получают эти колонки через ensure_schema().
_USER_COLUMNS = (
    ("goal_freezes_available", sa.Integer(), "2"),
    ("goal_best_streak", sa.Integer(), "0"),
    ("goal_rewards_granted", sa.String(), None),
)


def _table_names() -> set:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set:
    """Колонки таблицы; пустое множество, если таблицы ещё нет.

    На ЧИСТОЙ базе таблицы создаёт 0004_schema_baseline (идёт после),
    поэтому get_columns() без проверки бросал бы NoSuchTableError.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    tables = _table_names()

    # На ЧИСТОЙ базе таблиц ещё нет — их целиком создаст 0004_schema_baseline.
    # Пытаться создать goal_days здесь нельзя: FK ссылается на users.id,
    # которого пока не существует, и миграция упадёт.
    if "users" not in tables:
        return

    # ---- Таблица снимков дня ----
    # Идемпотентно: create_all()/ensure_schema() мог создать таблицу раньше.
    if "goal_days" not in tables:
        op.create_table(
            "goal_days",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "date",
                sa.Date(),
                nullable=False,
                index=True,
                server_default=sa.func.current_date(),
            ),
            sa.Column("status", sa.String(), nullable=False, server_default="missed"),
            sa.Column("sparks", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("meals_done", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("water_done", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("protein_done", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user_id", "date", name="uq_goal_day_user_date"),
        )

    # ---- Колонки пользователя ----
    existing = _existing_columns("users")
    for name, type_, default in _USER_COLUMNS:
        if name not in existing:
            op.add_column(
                "users",
                sa.Column(name, type_, nullable=True, server_default=default),
            )


def downgrade() -> None:
    existing = _existing_columns("users")
    for name, _type, _default in reversed(_USER_COLUMNS):
        if name in existing:
            op.drop_column("users", name)

    if "goal_days" in _table_names():
        op.drop_table("goal_days")
