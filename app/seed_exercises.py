# app/seed_exercises.py
"""Засев справочника упражнений (идемпотентно, по аналогии с seed_products).

kcal_per_min — примерный расход калорий в минуту для человека ~70 кг,
оценка по MET (kcal/мин ≈ MET × 3.5 × 70 / 200). Значения округлены.
Пример: «Жим лёжа» 6 ккал/мин → 30 минут ≈ 180 ккал.
"""

import logging

from app import models

logger = logging.getLogger(__name__)

# (название, категория, ккал/мин)
EXERCISES: list[tuple[str, str, float]] = [
    # ---------- Кардио ----------
    ("Бег, лёгкий темп (8 км/ч)", "cardio", 8.5),
    ("Бег, средний темп (10 км/ч)", "cardio", 10.5),
    ("Бег, быстрый темп (12+ км/ч)", "cardio", 12.5),
    ("Интервальный бег (HIIT)", "cardio", 12.0),
    ("Ходьба прогулочная", "cardio", 3.0),
    ("Ходьба быстрая", "cardio", 4.5),
    ("Скандинавская ходьба", "cardio", 5.5),
    ("Ходьба по лестнице", "cardio", 8.0),
    ("Велосипед, лёгкий темп", "cardio", 5.5),
    ("Велосипед, средний темп", "cardio", 8.0),
    ("Велотренажёр", "cardio", 7.0),
    ("Беговая дорожка", "cardio", 8.0),
    ("Эллиптический тренажёр", "cardio", 6.5),
    ("Гребной тренажёр", "cardio", 8.5),
    ("Степпер", "cardio", 7.0),
    ("Прыжки на скакалке", "cardio", 12.0),
    ("Плавание, лёгкое", "cardio", 6.0),
    ("Плавание, свободный стиль", "cardio", 9.0),
    # ---------- Силовые ----------
    ("Жим лёжа", "strength", 6.0),
    ("Приседания со штангой", "strength", 7.0),
    ("Становая тяга", "strength", 7.0),
    ("Армейский жим (жим стоя)", "strength", 6.0),
    ("Тяга штанги в наклоне", "strength", 6.0),
    ("Подтягивания", "strength", 8.0),
    ("Отжимания", "strength", 7.0),
    ("Отжимания на брусьях", "strength", 7.5),
    ("Выпады с гантелями", "strength", 6.5),
    ("Жим гантелей сидя", "strength", 5.5),
    ("Тяга верхнего блока", "strength", 5.5),
    ("Жим ногами в тренажёре", "strength", 6.0),
    ("Сгибания на бицепс", "strength", 4.5),
    ("Французский жим", "strength", 4.5),
    ("Приседания без веса", "strength", 5.5),
    ("Берпи", "strength", 10.0),
    ("Планка", "strength", 4.0),
    ("Скручивания на пресс", "strength", 4.5),
    ("Ягодичный мостик", "strength", 4.5),
    ("Круговая силовая тренировка", "strength", 8.0),
    ("Тренировка с гирями", "strength", 9.5),
    ("Кроссфит (WOD)", "strength", 11.0),
    # ---------- Фитнес / растяжка ----------
    ("Йога", "stretching", 3.0),
    ("Пилатес", "stretching", 3.5),
    ("Растяжка (стретчинг)", "stretching", 2.5),
    ("Аэробика", "cardio", 7.0),
    ("Зумба", "cardio", 7.5),
    ("Танцы", "cardio", 6.0),
    # ---------- Спорт ----------
    ("Футбол", "sport", 8.5),
    ("Баскетбол", "sport", 8.0),
    ("Волейбол", "sport", 4.5),
    ("Теннис", "sport", 8.0),
    ("Настольный теннис", "sport", 4.5),
    ("Бадминтон", "sport", 5.5),
    ("Бокс (работа с мешком)", "sport", 8.0),
    ("Единоборства", "sport", 10.0),
    ("Катание на коньках", "sport", 7.0),
    ("Беговые лыжи", "sport", 9.0),
    ("Сноуборд / горные лыжи", "sport", 5.5),
    ("Скалолазание", "sport", 9.0),
]


def seed_exercises(session) -> None:
    """Добавляет недостающие упражнения; существующие не трогает."""
    try:
        existing = {name for (name,) in session.query(models.Exercise.name).all()}
        added = 0
        for name, category, kcal_per_min in EXERCISES:
            if name in existing:
                continue
            session.add(
                models.Exercise(name=name, category=category, kcal_per_min=kcal_per_min)
            )
            added += 1
        if added:
            session.commit()
            logger.info("Seeded %d exercises", added)
    except Exception:
        session.rollback()
        logger.warning("Exercise seeding failed", exc_info=True)
        raise
