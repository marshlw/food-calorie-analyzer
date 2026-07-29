"""add weight goal columns to users (goal, rate, target weight)

Цель по весу определяет суточную норму КБЖУ: из неё считается дефицит или
профицит калорий и профиль макронутриентов (см. app/nutrition.py).

Колонки nullable без server_default: NULL трактуется расчётом как
«поддержание веса с дефолтным темпом», поэтому существующие пользователи
после миграции получают ровно ту же норму, что и раньше (TDEE).

Revision ID: 0002_user_goal
Revises: 0001_drop_legacy_meals
Create Date: 2026-07-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_user_goal"
down_revision: Union[str, None] = "0001_drop_legacy_meals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Имя -> тип. Тот же набор, что и в database._PROFILE_COLUMNS: проекты без
# Alembic получают эти колонки через ensure_schema().
_COLUMNS = (
    ("goal", sa.String()),                    # lose | maintain | gain
    ("goal_rate_kg_per_week", sa.Float()),    # желаемый темп, кг/нед
    ("target_weight_kg", sa.Float()),         # желаемый вес, кг
)


def _existing_columns() -> set:
    """Колонки users; пустое множество, если таблицы ещё нет.

    На ЧИСТОЙ базе таблицы создаёт миграция 0004_schema_baseline, которая
    идёт ПОСЛЕ этой. Без проверки get_columns("users") бросал бы
    NoSuchTableError и деплой на новом окружении падал бы целиком.
    """
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "users" not in inspector.get_table_names():
        return set()
    return {c["name"] for c in inspector.get_columns("users")}


def upgrade() -> None:
    # Идемпотентно: ensure_schema() мог долить колонки раньше миграции.
    existing = _existing_columns()
    if not existing:
        return  # чистая база — таблицу с этими колонками создаст 0004
    for name, type_ in _COLUMNS:
        if name not in existing:
            op.add_column("users", sa.Column(name, type_, nullable=True))


def downgrade() -> None:
    existing = _existing_columns()
    for name, _ in reversed(_COLUMNS):
        if name in existing:
            op.drop_column("users", name)
