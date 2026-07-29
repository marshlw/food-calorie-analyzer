"""Одноразовая подготовка данных после миграций (H-7).

Раньше засев справочников и backfill выполнялись в startup-хуке FastAPI —
то есть при старте КАЖДОГО uvicorn-воркера и КАЖДОГО рестарта контейнера.
Два воркера делали это одновременно, а backfill вычитывал в память Python
все подходящие строки meal_entries: при 5000 DAU (~20 000 строк/сутки) это
превращалось в многосекундную задержку деплоя.

Теперь это отдельный шаг деплоя, ровно один раз:

    alembic upgrade head && python -m app.bootstrap

Запускается сервисом `migrate` в docker-compose.prod.yml, до старта api и
celery. Все операции идемпотентны — повторный запуск безопасен.
"""
import logging
import sys

from . import crud
from .database import SessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("app.bootstrap")


def seed_reference_data() -> None:
    """Справочники продуктов (КБЖУ на 100 г) и упражнений (ккал/мин)."""
    from .seed_products import seed_products
    from .seed_exercises import seed_exercises

    session = SessionLocal()
    try:
        seed_products(session)
        logger.info("Products seeded")
        seed_exercises(session)
        logger.info("Exercises seeded")
    finally:
        session.close()


def backfill_protein_split() -> None:
    """Разметка животного/растительного белка у приёмов, добавленных до
    появления фичи. Идемпотентно — размечает только строки без разметки."""
    session = SessionLocal()
    try:
        updated = crud.backfill_meal_protein_split(session)
        logger.info("Backfilled protein split for %s meal rows", updated)
    finally:
        session.close()


STEPS = (
    ("seed reference data", seed_reference_data),
    ("backfill protein split", backfill_protein_split),
)


def main() -> int:
    failed = []
    for label, step in STEPS:
        try:
            step()
        except Exception:
            # Один упавший шаг не должен блокировать остальные и деплой:
            # это подготовка ДАННЫХ, а не схемы. Но код возврата ставим
            # ненулевой, чтобы CI/логи деплоя это заметили.
            logger.exception("Bootstrap step failed: %s", label)
            failed.append(label)

    if failed:
        logger.error("Bootstrap finished with errors: %s", ", ".join(failed))
        return 1

    logger.info("Bootstrap finished successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
