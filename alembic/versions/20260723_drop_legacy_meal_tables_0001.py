"""drop legacy meal tables (meals, meal_items, photos)

Эти таблицы — остатки старой модели приёма пищи. Приложение их не использует:
реальный дневник ведётся по цепочке daily_logs -> meal_entries -> meal_entry_items,
а фото хранятся в meal_entries.photo_path / tasks.image_path. Таблицы всегда
пустые, поэтому дроп безопасен.

Идемпотентно (DROP ... IF EXISTS): на «чистой» БД, где create_all их уже не
создаёт (модели удалены), миграция просто ничего не делает.

Revision ID: 0001_drop_legacy_meals
Revises:
Create Date: 2026-07-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = "0001_drop_legacy_meals"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Порядок с учётом внешних ключей: photos -> meal_items -> meals.
    # CASCADE подчищает FK-зависимости, если они остались от старой схемы.
    op.execute("DROP TABLE IF EXISTS photos CASCADE")
    op.execute("DROP TABLE IF EXISTS meal_items CASCADE")
    op.execute("DROP TABLE IF EXISTS meals CASCADE")


def downgrade() -> None:
    # Воссоздаём пустые структуры (данных в них не было). Форма повторяет
    # старые модели Meal / MealItem / Photo на момент удаления.
    op.create_table(
        "meals",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), server_default=func.now()),
        sa.Column("meal_type", sa.String(), server_default="meal"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total_calories", sa.Float(), server_default="0"),
        sa.Column("total_protein", sa.Float(), server_default="0"),
        sa.Column("total_protein_animal", sa.Float(), server_default="0"),
        sa.Column("total_protein_plant", sa.Float(), server_default="0"),
        sa.Column("total_fat", sa.Float(), server_default="0"),
        sa.Column("total_carbs", sa.Float(), server_default="0"),
    )
    op.create_index("ix_meals_user_id", "meals", ["user_id"])

    op.create_table(
        "meal_items",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("meal_id", sa.Integer(), sa.ForeignKey("meals.id"), nullable=False),
        sa.Column("food_name", sa.String(), nullable=False),
        sa.Column("quantity_g", sa.Float(), nullable=False),
        sa.Column("calories", sa.Float(), nullable=False),
        sa.Column("protein_g", sa.Float(), nullable=False),
        sa.Column("protein_animal_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("protein_plant_g", sa.Float(), nullable=False, server_default="0"),
        sa.Column("fat_g", sa.Float(), nullable=False),
        sa.Column("carbs_g", sa.Float(), nullable=False),
        sa.Column("source", sa.String(), server_default="ml"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
    )

    op.create_table(
        "photos",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "meal_item_id",
            sa.Integer(),
            sa.ForeignKey("meal_items.id"),
            unique=True,
            nullable=False,
        ),
        sa.Column("storage_path", sa.String(), nullable=False),
        sa.Column("thumbnail_path", sa.String(), nullable=True),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("original_filename", sa.String(), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=func.now()),
    )
    op.create_index("ix_photos_file_hash", "photos", ["file_hash"])
