# app/crud.py

from sqlalchemy import func as sa_func
from sqlalchemy.orm import selectinload, Session
from typing import List, Optional, Dict, Any, Tuple
import uuid
from datetime import datetime, date, timedelta
from . import models, schemas
import logging

import json

logger = logging.getLogger(__name__)

# ==================== UTILS ====================

def normalize_name(name: str) -> str:
    return name.lower().strip()

def safe_float(v, default=0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def escape_like(value: str) -> str:
    """Экранирует спецсимволы LIKE/ILIKE (%, _, \\) в пользовательском вводе,
    чтобы «%%%» не превращался в полный скан с совпадением всего."""
    return (
        value.replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def get_user_by_email_sync(db: Session, email: str) -> Optional[models.User]:
    return db.query(models.User).filter(models.User.email == email).first()


def create_user_sync(db: Session, user: schemas.UserCreate, hashed_password: str) -> models.User:
    db_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password,
        height_cm=getattr(user, "height_cm", None),
        sex=getattr(user, "sex", None),
        birth_date=getattr(user, "birth_date", None),
        # Активность и цель с шага «Ваша цель» при регистрации: без них новый
        # пользователь увидел бы норму поддержания вместо нормы под задачу.
        activity_level=getattr(user, "activity_level", None),
        goal=getattr(user, "goal", None),
        goal_rate_kg_per_week=getattr(user, "goal_rate_kg_per_week", None),
        target_weight_kg=getattr(user, "target_weight_kg", None),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ==================== PROFILE / WEIGHT ====================

def compute_nutrition_targets(db: Session, user: models.User) -> Dict[str, Any]:
    """Единый расчёт суточных норм (BMR, калории, БЖУ, вода) ПОД ЦЕЛЬ
    пользователя. Используется профилем, дневником, водой, советчиком и
    тренировками — цифры везде совпадают. Текущий вес берётся из последней
    записи истории.

    Сама формула живёт в app/nutrition.py (чистый модуль без БД): цель
    (похудение/поддержание/набор) и желаемый темп превращаются в дефицит или
    профицит калорий, БЖУ считаются от массы тела с учётом цели.

    Ручные нормы пользователя (custom_* в профиле, важно для атлетов)
    имеют приоритет над авторасчётом — поэтому, заданные один раз,
    они автоматически подхватываются во всех формах."""
    from app import nutrition

    latest = get_latest_weight(db, user.id)
    weight = latest.weight_kg if latest else None

    plan = nutrition.build_plan(
        weight_kg=weight,
        height_cm=user.height_cm,
        age=nutrition.calc_age(user.birth_date),
        sex=user.sex,
        activity_level=user.activity_level,
        goal=user.goal,
        goal_rate_kg_per_week=user.goal_rate_kg_per_week,
        target_weight_kg=user.target_weight_kg,
    )

    bmr = plan.bmr
    calories = plan.calories
    macros = {"protein_g": plan.protein_g, "fat_g": plan.fat_g, "carbs_g": plan.carbs_g}
    water_ml = plan.water_ml

    # Переопределения из профиля (NULL/0 = использовать авторасчёт)
    if getattr(user, "custom_calorie_target", None):
        calories = user.custom_calorie_target
        # БЖУ по умолчанию следуют за ручной калорийностью — пересчитываем их
        # от этой калорийности, сохраняя профиль макросов под цель.
        macros = nutrition.calc_macro_targets(
            calories, weight_kg=weight, height_cm=user.height_cm,
            goal=user.goal, activity_level=user.activity_level,
        )
    # …но каждое из них тоже можно задать вручную по отдельности
    protein_g = getattr(user, "custom_protein_g", None) or macros["protein_g"]
    fat_g = getattr(user, "custom_fat_g", None) or macros["fat_g"]
    carbs_g = getattr(user, "custom_carbs_g", None) or macros["carbs_g"]
    if getattr(user, "custom_water_ml", None):
        water_ml = user.custom_water_ml

    # Разделение нормы белка на животный/растительный. По умолчанию делим общую
    # норму по доле PROTEIN_ANIMAL_TARGET_SHARE; любую из целей можно задать
    # вручную (custom_protein_animal_g / custom_protein_plant_g).
    from .protein_source import PROTEIN_ANIMAL_TARGET_SHARE
    if protein_g is not None:
        auto_animal = round(protein_g * PROTEIN_ANIMAL_TARGET_SHARE)
        auto_plant = round(protein_g - auto_animal)
    else:
        auto_animal = None
        auto_plant = None
    protein_animal_g = getattr(user, "custom_protein_animal_g", None) or auto_animal
    protein_plant_g = getattr(user, "custom_protein_plant_g", None) or auto_plant

    return {
        "bmr": bmr,
        # Норма поддержания (TDEE) до применения цели — фронт показывает её
        # рядом с итоговой нормой, чтобы дефицит/профицит был наглядным.
        "maintenance_calories": plan.tdee,
        "calories": calories,
        "protein_g": protein_g,
        "protein_animal_g": protein_animal_g,
        "protein_plant_g": protein_plant_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "water_ml": water_ml,
        "current_weight_kg": weight,
        "bmi": plan.bmi,
        "goal_plan": plan.goal_plan.as_dict() if plan.goal_plan else None,
        "warnings": plan.warnings,
    }


def get_latest_weight(db: Session, user_id: int) -> Optional[models.WeightRecord]:
    """Последнее взвешивание = источник правды для «текущего веса»."""
    return (
        db.query(models.WeightRecord)
        .filter(models.WeightRecord.user_id == user_id)
        .order_by(
            models.WeightRecord.recorded_on.desc(),
            models.WeightRecord.created_at.desc(),
        )
        .first()
    )


def list_weight_history(
    db: Session,
    user_id: int,
    start: Optional[date] = None,
    end: Optional[date] = None,
) -> List[models.WeightRecord]:
    q = db.query(models.WeightRecord).filter(models.WeightRecord.user_id == user_id)
    if start:
        q = q.filter(models.WeightRecord.recorded_on >= start)
    if end:
        q = q.filter(models.WeightRecord.recorded_on <= end)
    return q.order_by(models.WeightRecord.recorded_on.asc()).all()


def list_recent_weights(db: Session, user_id: int, n: int = 30) -> List[models.WeightRecord]:
    """Последние n взвешиваний (по возрастанию даты) — LIMIT в SQL,
    вместо выгрузки всей истории в Python."""
    rows = (
        db.query(models.WeightRecord)
        .filter(models.WeightRecord.user_id == user_id)
        .order_by(models.WeightRecord.recorded_on.desc())
        .limit(n)
        .all()
    )
    return list(reversed(rows))


# Обхваты тела, которые можно записать вместе с весом (см).
MEASUREMENT_FIELDS = ("waist_cm", "chest_cm", "hips_cm", "shoulders_cm")


def upsert_weight_record(
    db: Session,
    user_id: int,
    weight_kg: float,
    recorded_on: Optional[date] = None,
    note: Optional[str] = None,
    source: str = "manual",
    measurements: Optional[Dict[str, Any]] = None,
) -> models.WeightRecord:
    """Одна запись на (user, дата): повторное сохранение за тот же день
    обновляет существующую строку, а не создаёт дубль.

    measurements -- словарь обхватов тела (waist_cm/chest_cm/hips_cm/
    shoulders_cm). Значение None означает «не трогать»: при обновлении
    записи ранее заполненный обхват не затирается, если в этот раз его
    не прислали."""
    recorded_on = recorded_on or date.today()
    measurements = measurements or {}
    rec = (
        db.query(models.WeightRecord)
        .filter(
            models.WeightRecord.user_id == user_id,
            models.WeightRecord.recorded_on == recorded_on,
        )
        .first()
    )
    if rec:
        rec.weight_kg = weight_kg
        if note is not None:
            rec.note = note
        rec.source = source
        # Обновляем только присланные обхваты; остальные оставляем как есть.
        for field in MEASUREMENT_FIELDS:
            value = measurements.get(field)
            if value is not None:
                setattr(rec, field, value)
    else:
        rec = models.WeightRecord(
            user_id=user_id,
            weight_kg=weight_kg,
            recorded_on=recorded_on,
            note=note,
            source=source,
            **{f: measurements.get(f) for f in MEASUREMENT_FIELDS},
        )
        db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def get_weight_record(
    db: Session, user_id: int, record_id: int
) -> Optional[models.WeightRecord]:
    """Запись замера по id с проверкой владельца (чужие не отдаём)."""
    return (
        db.query(models.WeightRecord)
        .filter(
            models.WeightRecord.id == record_id,
            models.WeightRecord.user_id == user_id,
        )
        .first()
    )


class DuplicateDateError(Exception):
    """На эту дату у пользователя уже есть другая запись замера."""


def update_weight_record(
    db: Session,
    rec: models.WeightRecord,
    payload: schemas.WeightRecordUpdate,
) -> models.WeightRecord:
    """Редактирование записи замера. Обхваты задаются явно: None очищает
    значение (в форме пустое поле = убрать показатель). Смену даты
    блокируем, если на новую дату уже есть другая запись (uq user+date)."""
    if payload.recorded_on is not None and payload.recorded_on != rec.recorded_on:
        clash = (
            db.query(models.WeightRecord)
            .filter(
                models.WeightRecord.user_id == rec.user_id,
                models.WeightRecord.recorded_on == payload.recorded_on,
                models.WeightRecord.id != rec.id,
            )
            .first()
        )
        if clash is not None:
            raise DuplicateDateError()
        rec.recorded_on = payload.recorded_on

    rec.weight_kg = payload.weight_kg
    rec.note = payload.note
    for field in MEASUREMENT_FIELDS:
        setattr(rec, field, getattr(payload, field))

    db.commit()
    db.refresh(rec)
    return rec


def delete_weight_record(db: Session, rec: models.WeightRecord) -> None:
    db.delete(rec)
    db.commit()


def update_profile(db: Session, user: models.User, payload: schemas.ProfileUpdate) -> models.User:
    # Исторически auth.get_current_user и эндпоинты использовали РАЗНЫЕ
    # сессии, из-за чего коммит переданного объекта падал с "not persistent
    # within this Session". Сейчас зависимость get_db одна (app.database) и
    # сессия общая, но перечитывание оставлено как защита от передачи
    # detached-объекта (например, из фонового кода или тестов).
    db_user = db.query(models.User).filter(models.User.id == user.id).first()
    if db_user is None:
        raise ValueError(f"User {user.id} not found")

    if payload.full_name is not None:
        db_user.full_name = payload.full_name
    if payload.height_cm is not None:
        db_user.height_cm = payload.height_cm
    if payload.sex is not None:
        db_user.sex = payload.sex
    if payload.birth_date is not None:
        db_user.birth_date = payload.birth_date
    if payload.activity_level is not None:
        db_user.activity_level = payload.activity_level

    # Цель по весу. При СМЕНЕ цели сбрасываем ранее заданный темп (если новый
    # не пришёл в том же запросе): «0.5 кг/нед» на похудении — умеренный темп,
    # а на наборе — вдвое выше безопасного, переносить его между целями нельзя.
    if payload.goal is not None:
        if payload.goal != db_user.goal and payload.goal_rate_kg_per_week is None:
            db_user.goal_rate_kg_per_week = None
        db_user.goal = payload.goal

    # Темп и целевой вес: None = не менять, 0 = сбросить (дефолт/без финиша).
    for field in ("goal_rate_kg_per_week", "target_weight_kg"):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(db_user, field, value if value > 0 else None)

    # Ручные нормы КБЖУ/воды: None = не менять, 0 = сбросить на авторасчёт,
    # положительное значение = установить вручную.
    for field in (
        "custom_calorie_target",
        "custom_protein_g",
        "custom_protein_animal_g",
        "custom_protein_plant_g",
        "custom_fat_g",
        "custom_carbs_g",
        "custom_water_ml",
    ):
        value = getattr(payload, field, None)
        if value is not None:
            setattr(db_user, field, value if value > 0 else None)

    db.commit()

    # Вес и обхваты из профиля -> в историю (запись за сегодня, upsert'ом).
    # Обхваты хранятся на записи веса, поэтому им нужен вес: берём из формы,
    # иначе — последний известный. Пишем, если изменился вес ИЛИ заданы обхваты.
    measurements = {
        "waist_cm": payload.waist_cm,
        "chest_cm": payload.chest_cm,
        "hips_cm": payload.hips_cm,
        "shoulders_cm": payload.shoulders_cm,
    }
    has_measurements = any(v is not None for v in measurements.values())
    if payload.save_weight_as_record and (payload.weight_kg is not None or has_measurements):
        latest = get_latest_weight(db, db_user.id)
        weight_for_record = (
            payload.weight_kg if payload.weight_kg is not None
            else (latest.weight_kg if latest else None)
        )
        if weight_for_record is not None:
            weight_changed = latest is None or latest.weight_kg != weight_for_record
            if weight_changed or has_measurements:
                upsert_weight_record(
                    db,
                    db_user.id,
                    weight_for_record,
                    source="profile_edit",
                    measurements=measurements,
                )

    db.refresh(db_user)
    return db_user


def create_task(db: Session, user_id: int, image_path: str, image_hash: Optional[str] = None) -> models.Task:
    task_id = str(uuid.uuid4())
    task = models.Task(
        id=task_id,
        user_id=user_id,
        image_path=image_path,
        status=models.TaskStatus.PENDING,
        image_hash=image_hash
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def get_task(db: Session, task_id: str) -> Optional[models.Task]:
    return db.query(models.Task).filter(models.Task.id == task_id).first()


def update_task(
    db: Session,
    task_id: str,
    status: models.TaskStatus,
    result: Optional[dict] = None,
    error: Optional[str] = None
) -> Optional[models.Task]:

    task = get_task(db, task_id)
    if not task:
        return None

    if result is not None:
        task.result_json = json.dumps(result, ensure_ascii=False)

    if error:
        task.error = error

    task.status = status
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return task


def get_tasks_by_user_sync(db: Session, user_id: int, limit: int = 50, offset: int = 0) -> List[models.Task]:
    return (
        db.query(models.Task)
        .filter(models.Task.user_id == user_id)
        .order_by(models.Task.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_task_by_id_sync(db: Session, task_id: str) -> Optional[models.Task]:
    return db.query(models.Task).filter(models.Task.id == task_id).first()


def get_or_create_daily_log(db: Session, user_id: int, date_value: date) -> models.DailyLog:
    daily_log = db.query(models.DailyLog).filter(
        models.DailyLog.user_id == user_id,
        models.DailyLog.date == date_value
    ).first()

    if daily_log:
        return daily_log

    daily_log = models.DailyLog(
        user_id=user_id,
        date=date_value
    )
    db.add(daily_log)
    db.commit()
    db.refresh(daily_log)
    return daily_log


def resolve_protein_split(food_name: str, protein_g: float, animal, plant) -> tuple:
    """Возвращает (животный, растительный) белок в граммах.

    Если явное разделение уже задано (пользователь выбрал тип блюда или оно
    пришло из справочника/AI) — используем его. Иначе определяем источник
    автоматически по названию блюда (тот же классификатор, что и для базы
    продуктов), чтобы разбивка была даже без ручного выбора типа."""
    a = animal or 0
    p = plant or 0
    if a > 0 or p > 0:
        return round(a, 1), round(p, 1)
    if (protein_g or 0) <= 0:
        return 0.0, 0.0
    from .protein_source import classify, split_protein
    return split_protein(protein_g, classify(food_name or ""))


def _meal_totals_from_items(items: List[schemas.MealEntryItemCreate]) -> Dict[str, float]:
    """Итоги составного приёма: суммы КБЖУ/веса по блюдам (включая разделение
    белка на животный/растительный — с авто-определением источника по названию)."""
    splits = [
        resolve_protein_split(
            i.food_name, i.protein_g,
            getattr(i, "protein_animal_g", 0), getattr(i, "protein_plant_g", 0),
        )
        for i in items
    ]
    return {
        "calories": round(sum(i.calories for i in items), 1),
        "protein_g": round(sum(i.protein_g for i in items), 1),
        "protein_animal_g": round(sum(a for a, _ in splits), 1),
        "protein_plant_g": round(sum(p for _, p in splits), 1),
        "fat_g": round(sum(i.fat_g for i in items), 1),
        "carbs_g": round(sum(i.carbs_g for i in items), 1),
        "weight_g": round(sum(i.weight_g for i in items), 1),
    }


def add_meal_entry(db: Session, user_id: int, meal_data: schemas.MealEntryCreate, target_date: Optional[date] = None, task_id: Optional[str] = None) -> models.MealEntry:
    target_date = target_date or date.today()
    daily_log = get_or_create_daily_log(db, user_id, target_date)

    items = getattr(meal_data, "items", None) or []
    # У составного приёма итоги считаем на бэкенде — фронту не доверяем суммы.
    if items:
        totals = _meal_totals_from_items(items)
    else:
        entry_animal, entry_plant = resolve_protein_split(
            meal_data.food_name, meal_data.protein_g,
            getattr(meal_data, "protein_animal_g", 0), getattr(meal_data, "protein_plant_g", 0),
        )
        totals = {
            "calories": meal_data.calories,
            "protein_g": meal_data.protein_g,
            "protein_animal_g": entry_animal,
            "protein_plant_g": entry_plant,
            "fat_g": meal_data.fat_g,
            "carbs_g": meal_data.carbs_g,
            "weight_g": meal_data.weight_g,
        }

    meal_entry = models.MealEntry(
        daily_log_id=daily_log.id,
        food_name=meal_data.food_name,
        calories=totals["calories"],
        protein_g=totals["protein_g"],
        protein_animal_g=totals["protein_animal_g"],
        protein_plant_g=totals["protein_plant_g"],
        fat_g=totals["fat_g"],
        carbs_g=totals["carbs_g"],
        weight_g=totals["weight_g"],
        meal_type=getattr(meal_data, 'meal_type', 'snacks'),
        task_id=task_id
    )
    for item in items:
        i_animal, i_plant = resolve_protein_split(
            item.food_name, item.protein_g,
            getattr(item, "protein_animal_g", 0), getattr(item, "protein_plant_g", 0),
        )
        meal_entry.items.append(models.MealEntryItem(
            food_name=item.food_name,
            weight_g=item.weight_g,
            calories=item.calories,
            protein_g=item.protein_g,
            protein_animal_g=i_animal,
            protein_plant_g=i_plant,
            fat_g=item.fat_g,
            carbs_g=item.carbs_g,
        ))
    db.add(meal_entry)
    db.commit()
    db.refresh(meal_entry)
    return meal_entry


def update_meal_entry(db: Session, meal_entry: models.MealEntry, update: schemas.MealEntryCreate) -> models.MealEntry:
    """Обновление записи приёма. Если переданы items — полная замена блюд
    с пересчётом итогов; иначе обновляются только поля записи."""
    items = getattr(update, "items", None) or []
    if items:
        totals = _meal_totals_from_items(items)
        meal_entry.items.clear()
        for item in items:
            i_animal, i_plant = resolve_protein_split(
                item.food_name, item.protein_g,
                getattr(item, "protein_animal_g", 0), getattr(item, "protein_plant_g", 0),
            )
            meal_entry.items.append(models.MealEntryItem(
                food_name=item.food_name,
                weight_g=item.weight_g,
                calories=item.calories,
                protein_g=item.protein_g,
                protein_animal_g=i_animal,
                protein_plant_g=i_plant,
                fat_g=item.fat_g,
                carbs_g=item.carbs_g,
            ))
        meal_entry.calories = totals["calories"]
        meal_entry.protein_g = totals["protein_g"]
        meal_entry.protein_animal_g = totals["protein_animal_g"]
        meal_entry.protein_plant_g = totals["protein_plant_g"]
        meal_entry.fat_g = totals["fat_g"]
        meal_entry.carbs_g = totals["carbs_g"]
        meal_entry.weight_g = totals["weight_g"]
    else:
        # Простая запись: если раньше была составной — блюда убираем,
        # запись становится обычной с введёнными вручную итогами.
        meal_entry.items.clear()
        u_animal, u_plant = resolve_protein_split(
            update.food_name, update.protein_g,
            getattr(update, "protein_animal_g", 0), getattr(update, "protein_plant_g", 0),
        )
        meal_entry.calories = update.calories
        meal_entry.protein_g = update.protein_g
        meal_entry.protein_animal_g = u_animal
        meal_entry.protein_plant_g = u_plant
        meal_entry.fat_g = update.fat_g
        meal_entry.carbs_g = update.carbs_g
        meal_entry.weight_g = update.weight_g

    meal_entry.food_name = update.food_name
    meal_entry.meal_type = getattr(update, 'meal_type', meal_entry.meal_type)

    db.commit()
    db.refresh(meal_entry)
    return meal_entry


def get_daily_log(db: Session, user_id: int, date_value: date) -> Optional[models.DailyLog]:
    return db.query(models.DailyLog).options(
        selectinload(models.DailyLog.entries).selectinload(models.MealEntry.items),
        # task нужен для photo_url (фото AI-анализа) — грузим без N+1
        selectinload(models.DailyLog.entries).selectinload(models.MealEntry.task),
    ).filter(
        models.DailyLog.user_id == user_id,
        models.DailyLog.date == date_value
    ).first()


def get_meal_entry_sync(db: Session, meal_entry_id: int) -> Optional[models.MealEntry]:
    return db.query(models.MealEntry).filter(models.MealEntry.id == meal_entry_id).first()


def backfill_meal_protein_split(db: Session) -> int:
    """Проставляет разделение белка (животный/растительный) существующим приёмам,
    у которых оно ещё не заполнено — определяя источник по названию блюда.
    Идемпотентно: строки с уже заданным разделением пропускаются.
    Возвращает число обновлённых записей/блюд."""
    from .protein_source import classify, split_protein

    updated = 0

    # 1) Блюда составных приёмов
    items = (
        db.query(models.MealEntryItem)
        .filter(
            ((models.MealEntryItem.protein_animal_g == None) | (models.MealEntryItem.protein_animal_g == 0)),  # noqa: E711
            ((models.MealEntryItem.protein_plant_g == None) | (models.MealEntryItem.protein_plant_g == 0)),    # noqa: E711
            models.MealEntryItem.protein_g > 0,
        )
        .all()
    )
    for it in items:
        a, p = split_protein(it.protein_g, classify(it.food_name))
        it.protein_animal_g, it.protein_plant_g = a, p
        updated += 1

    # 2) Записи приёмов
    entries = (
        db.query(models.MealEntry)
        .filter(
            ((models.MealEntry.protein_animal_g == None) | (models.MealEntry.protein_animal_g == 0)),  # noqa: E711
            ((models.MealEntry.protein_plant_g == None) | (models.MealEntry.protein_plant_g == 0)),    # noqa: E711
            models.MealEntry.protein_g > 0,
        )
        .all()
    )
    for e in entries:
        if e.items:
            # Составной приём: итог = сумма по блюдам (они уже размечены выше).
            e.protein_animal_g = round(sum((i.protein_animal_g or 0) for i in e.items), 1)
            e.protein_plant_g = round(sum((i.protein_plant_g or 0) for i in e.items), 1)
        else:
            a, p = split_protein(e.protein_g, classify(e.food_name))
            e.protein_animal_g, e.protein_plant_g = a, p
        updated += 1

    if updated:
        db.commit()
    return updated


def calculate_daily_totals(log: models.DailyLog) -> Dict[str, float]:
    total_calories = 0.0
    total_protein = 0.0
    total_protein_animal = 0.0
    total_protein_plant = 0.0
    total_fat = 0.0
    total_carbs = 0.0

    for entry in log.entries:
        total_calories += entry.calories
        total_protein += entry.protein_g
        total_protein_animal += getattr(entry, "protein_animal_g", 0) or 0
        total_protein_plant += getattr(entry, "protein_plant_g", 0) or 0
        total_fat += entry.fat_g
        total_carbs += entry.carbs_g

    return {
        "total_calories": round(total_calories, 1),
        "total_protein": round(total_protein, 1),
        "total_protein_animal": round(total_protein_animal, 1),
        "total_protein_plant": round(total_protein_plant, 1),
        "total_fat": round(total_fat, 1),
        "total_carbs": round(total_carbs, 1)
    }


# ==================== WATER ====================

def get_water_log(db: Session, user_id: int, date_value: date) -> Optional[models.WaterLog]:
    return (
        db.query(models.WaterLog)
        .filter(
            models.WaterLog.user_id == user_id,
            models.WaterLog.date == date_value,
        )
        .first()
    )


def get_water_total(db: Session, user_id: int, date_value: date) -> float:
    """Сколько выпито за день (мл). 0, если записи ещё нет."""
    log = get_water_log(db, user_id, date_value)
    return float(log.total_ml) if log else 0.0


def adjust_water(
    db: Session,
    user_id: int,
    amount_ml: float,
    date_value: Optional[date] = None,
) -> models.WaterLog:
    """Прибавляет (или убавляет при отрицательном amount_ml) воду за день.
    Одна строка на (user, дата) — upsert; итог не опускается ниже нуля."""
    date_value = date_value or date.today()
    log = get_water_log(db, user_id, date_value)
    if log is None:
        log = models.WaterLog(user_id=user_id, date=date_value, total_ml=0)
        db.add(log)

    log.total_ml = max(0.0, float(log.total_ml or 0) + amount_ml)
    db.commit()
    db.refresh(log)
    return log


# ==================== GOALS (цель дня, серия, путь) ====================
#
# Правила живут в app/goals.py (чистый модуль без БД). Здесь — только доступ
# к данным: агрегаты по дням, ленивый синк снимков goal_days и заморозки.

# Сколько дней назад досинхронизировать при обычном запросе. Покрывает и
# самую длинную реалистичную серию, и «дыры» у пользователей, заведённых до
# появления фичи: строки создаются один раз, дальше запись почти не идёт.
GOALS_SYNC_WINDOW_DAYS: int = 120


def meal_day_aggregates(
    db: Session, user_id: int, start: date, end: date
) -> Dict[date, Tuple[int, float]]:
    """Дата -> (число записей, суммарный белок, г) за период.
    Один групповой запрос вместо N запросов дневника."""
    rows = (
        db.query(
            models.DailyLog.date.label("day"),
            sa_func.count(models.MealEntry.id).label("cnt"),
            sa_func.coalesce(sa_func.sum(models.MealEntry.protein_g), 0.0).label("protein"),
        )
        .join(models.MealEntry, models.MealEntry.daily_log_id == models.DailyLog.id)
        .filter(
            models.DailyLog.user_id == user_id,
            models.DailyLog.date >= start,
            models.DailyLog.date <= end,
        )
        .group_by(models.DailyLog.date)
        .all()
    )
    return {row.day: (int(row.cnt or 0), float(row.protein or 0)) for row in rows}


def water_day_totals(db: Session, user_id: int, start: date, end: date) -> Dict[date, float]:
    """Дата -> выпито мл за период."""
    rows = (
        db.query(models.WaterLog.date, models.WaterLog.total_ml)
        .filter(
            models.WaterLog.user_id == user_id,
            models.WaterLog.date >= start,
            models.WaterLog.date <= end,
        )
        .all()
    )
    return {row[0]: float(row[1] or 0) for row in rows}


def list_goal_days(
    db: Session, user_id: int, start: date, end: date
) -> Dict[date, models.GoalDay]:
    rows = (
        db.query(models.GoalDay)
        .filter(
            models.GoalDay.user_id == user_id,
            models.GoalDay.date >= start,
            models.GoalDay.date <= end,
        )
        .all()
    )
    return {row.date: row for row in rows}


def build_day_goals(
    db: Session,
    user: models.User,
    day: date,
    *,
    targets: Optional[Dict[str, Any]] = None,
) -> list:
    """Цели дня (список goals.DailyGoal) по фактическим записям за дату."""
    from . import goals as goals_rules

    targets = targets if targets is not None else compute_nutrition_targets(db, user)
    meals = meal_day_aggregates(db, user.id, day, day).get(day, (0, 0.0))
    water_ml = water_day_totals(db, user.id, day, day).get(day, 0.0)

    return goals_rules.build_daily_goals(
        meals_count=meals[0],
        water_ml=water_ml,
        water_target_ml=targets.get("water_ml"),
        protein_g=meals[1],
        protein_target_g=targets.get("protein_g"),
    )


def sync_goal_days(
    db: Session,
    user: models.User,
    start: date,
    end: date,
    *,
    targets: Optional[Dict[str, Any]] = None,
) -> Dict[date, models.GoalDay]:
    """Пересчитывает и сохраняет снимки дней за период [start; end].

    Строка создаётся ТОЛЬКО для дня с активностью (есть приёмы или вода) —
    пустые дни выводятся как «пропуск» по отсутствию строки, поэтому таблица
    не растёт на каждого молчащего пользователя. Уже существующие строки
    обновляются, если пересчёт дал другие цифры; `frozen` при этом липкий.

    Будущие дни не сохраняются: у них нет фактов, а статус `future` вычисляется
    на лету.
    """
    from . import goals as goals_rules

    today = date.today()
    if end > today:
        end = today
    if start > end:
        return {}

    targets = targets if targets is not None else compute_nutrition_targets(db, user)
    water_target = targets.get("water_ml")
    protein_target = targets.get("protein_g")

    meals = meal_day_aggregates(db, user.id, start, end)
    water = water_day_totals(db, user.id, start, end)
    existing = list_goal_days(db, user.id, start, end)

    dirty = False
    result: Dict[date, models.GoalDay] = {}

    day = start
    while day <= end:
        row = existing.get(day)
        meals_count, protein_g = meals.get(day, (0, 0.0))
        water_ml = water.get(day, 0.0)
        has_activity = meals_count > 0 or water_ml > 0

        if row is None and not has_activity:
            day += timedelta(days=1)
            continue

        day_goals = goals_rules.build_daily_goals(
            meals_count=meals_count,
            water_ml=water_ml,
            water_target_ml=water_target,
            protein_g=protein_g,
            protein_target_g=protein_target,
        )
        by_id = {g.id: g for g in day_goals}
        frozen = bool(row.frozen) if row is not None else False
        status = goals_rules.resolve_status(day_goals, frozen=frozen, day=day, today=today)
        sparks = goals_rules.count_sparks(day_goals)

        if row is None:
            row = models.GoalDay(user_id=user.id, date=day)
            db.add(row)
            dirty = True

        new_values = {
            "status": status,
            "sparks": sparks,
            "meals_done": by_id[goals_rules.GOAL_MEALS].done,
            "water_done": by_id[goals_rules.GOAL_WATER].done,
            "protein_done": by_id[goals_rules.GOAL_PROTEIN].done,
        }
        for field, value in new_values.items():
            if getattr(row, field, None) != value:
                setattr(row, field, value)
                dirty = True

        result[day] = row
        day += timedelta(days=1)

    if dirty:
        db.commit()

    return result


def goal_status_map(
    db: Session, user_id: int, start: date, end: date
) -> Dict[date, str]:
    """Дата -> статус для расчёта серии. Отсутствие строки = пропуск."""
    return {d: row.status for d, row in list_goal_days(db, user_id, start, end).items()}


def refresh_goal_progress(
    db: Session,
    user: models.User,
    *,
    today: Optional[date] = None,
    extra_start: Optional[date] = None,
    targets: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Досинхронизирует окно дней, считает серию/рекорд и выдаёт награды.

    extra_start расширяет окно синка назад (нужно вкладке «Путь», когда
    пользователь листает старый месяц).
    Возвращает {'streak', 'best_streak', 'statuses', 'targets'}.
    """
    from . import goals as goals_rules

    today = today or date.today()
    targets = targets if targets is not None else compute_nutrition_targets(db, user)

    start = today - timedelta(days=GOALS_SYNC_WINDOW_DAYS)
    if extra_start and extra_start < start:
        start = extra_start

    sync_goal_days(db, user, start, today, targets=targets)
    statuses = goal_status_map(db, user.id, start, today)

    streak = goals_rules.compute_streak(statuses, today)
    best_streak = max(int(user.goal_best_streak or 0), streak,
                      goals_rules.compute_best_streak(statuses))

    grant_goal_rewards(db, user, streak=streak, best_streak=best_streak)

    return {
        "streak": streak,
        "best_streak": int(user.goal_best_streak or 0),
        "statuses": statuses,
        "targets": targets,
    }


def grant_goal_rewards(
    db: Session, user: models.User, *, streak: int, best_streak: int
) -> List[str]:
    """Начисляет бонусные заморозки за впервые взятые вехи серии и
    обновляет рекорд. Идемпотентно: коды выданных наград хранятся в
    users.goal_rewards_granted, поэтому повторный пересчёт ничего не даёт."""
    from . import goals as goals_rules

    granted = {c for c in (user.goal_rewards_granted or "").split(",") if c}
    newly: List[str] = []
    bonus = 0

    for rule in goals_rules.REWARDS:
        if rule.code in granted:
            continue
        if max(streak, best_streak) >= rule.threshold:
            granted.add(rule.code)
            newly.append(rule.code)
            bonus += rule.bonus_freezes

    changed = False
    if newly:
        user.goal_rewards_granted = ",".join(sorted(granted))
        changed = True
    if bonus:
        user.goal_freezes_available = int(user.goal_freezes_available or 0) + bonus
        changed = True
    if best_streak > int(user.goal_best_streak or 0):
        user.goal_best_streak = best_streak
        changed = True

    if changed:
        db.commit()
        db.refresh(user)

    return newly


class FreezeError(Exception):
    """Заморозку применить нельзя (нет запаса, день закрыт, слишком старый)."""


def apply_goal_freeze(db: Session, user: models.User, day: date) -> models.GoalDay:
    """Тратит одну заморозку и помечает день сохранённым.
    Бросает FreezeError с человекочитаемым текстом, если это невозможно."""
    from . import goals as goals_rules

    today = date.today()
    row = list_goal_days(db, user.id, day, day).get(day)
    current_status = row.status if row else goals_rules.STATUS_MISSED

    problem = goals_rules.can_freeze(
        day, today, current_status, int(user.goal_freezes_available or 0)
    )
    if problem:
        raise FreezeError(problem)

    if row is None:
        row = models.GoalDay(user_id=user.id, date=day, sparks=0)
        db.add(row)

    row.frozen = True
    row.status = goals_rules.STATUS_FROZEN
    user.goal_freezes_available = int(user.goal_freezes_available or 0) - 1

    db.commit()
    db.refresh(row)
    return row


# ==================== WORKOUTS ====================

def add_workout(db: Session, user_id: int, payload: schemas.WorkoutCreate) -> models.Workout:
    """Создание записи тренировки на выбранный день (по умолчанию — сегодня).
    Для составной тренировки (items) итоги по времени/калориям суммируются
    из упражнений на бэкенде."""
    items = payload.items or []
    if items:
        duration = round(sum(i.duration_min for i in items), 1)
        calories = round(sum(i.calories_burned for i in items), 1)
    else:
        duration = payload.duration_min
        calories = payload.calories_burned

    workout = models.Workout(
        user_id=user_id,
        date=payload.date or date.today(),
        workout_type=payload.workout_type,
        title=payload.title,
        description=payload.description,
        started_at=payload.started_at,
        duration_min=duration,
        calories_burned=calories,
    )
    for item in items:
        workout.items.append(models.WorkoutItem(
            name=item.name,
            duration_min=item.duration_min,
            calories_burned=item.calories_burned,
        ))
    db.add(workout)
    db.commit()
    db.refresh(workout)
    return workout


def list_workouts(db: Session, user_id: int, date_value: date) -> List[models.Workout]:
    return (
        db.query(models.Workout)
        .options(selectinload(models.Workout.items))
        .filter(models.Workout.user_id == user_id, models.Workout.date == date_value)
        .order_by(models.Workout.started_at.asc().nullslast(), models.Workout.created_at.asc())
        .all()
    )


def get_workout(db: Session, user_id: int, workout_id: int) -> Optional[models.Workout]:
    return (
        db.query(models.Workout)
        .filter(models.Workout.id == workout_id, models.Workout.user_id == user_id)
        .first()
    )


def workouts_day_totals(db: Session, user_id: int, date_value: date) -> Dict[str, float]:
    """Сводка активности за день (для карточки на вкладке «Тренировки»)."""
    workouts = list_workouts(db, user_id, date_value)
    return {
        "total_calories_burned": round(sum(w.calories_burned or 0 for w in workouts), 1),
        "total_duration_min": round(sum(w.duration_min or 0 for w in workouts), 1),
        "count": len(workouts),
    }


def workout_dates_in_range(db: Session, user_id: int, start: date, end: date) -> set:
    """Даты, в которые были тренировки (для точек в недельной полоске)."""
    rows = (
        db.query(models.Workout.date)
        .filter(
            models.Workout.user_id == user_id,
            models.Workout.date >= start,
            models.Workout.date <= end,
        )
        .distinct()
        .all()
    )
    return {r[0] for r in rows}


def search_exercises(db: Session, query: str = "", limit: int = 60) -> List[models.Exercise]:
    """Поиск по справочнику упражнений (для формы записи тренировки).
    Запрос разбивается на слова, каждое должно входить в название —
    порядок слов не важен («лёжа жим» находит «жим лёжа»).
    Пустой запрос — весь список по алфавиту."""
    q = db.query(models.Exercise)
    query = (query or "").strip().lower()
    limit = max(1, min(limit, 100))
    for word in query.split():
        q = q.filter(models.Exercise.name.ilike(f"%{escape_like(word)}%", escape="\\"))
    return q.order_by(models.Exercise.name.asc()).limit(limit).all()


def update_workout(db: Session, workout: models.Workout, payload: schemas.WorkoutCreate) -> models.Workout:
    """Обновление тренировки. Упражнения (items) заменяются целиком,
    итоги по времени/калориям пересчитываются на бэкенде — по аналогии
    с update_meal_entry для приёмов пищи."""
    items = payload.items or []
    if items:
        duration = round(sum(i.duration_min for i in items), 1)
        calories = round(sum(i.calories_burned for i in items), 1)
    else:
        duration = payload.duration_min
        calories = payload.calories_burned

    workout.items.clear()
    for item in items:
        workout.items.append(models.WorkoutItem(
            name=item.name,
            duration_min=item.duration_min,
            calories_burned=item.calories_burned,
        ))

    workout.workout_type = payload.workout_type
    workout.title = payload.title
    workout.description = payload.description
    workout.started_at = payload.started_at
    workout.duration_min = duration
    workout.calories_burned = calories
    if payload.date:
        workout.date = payload.date

    db.commit()
    db.refresh(workout)
    return workout


def delete_workout(db: Session, user_id: int, workout_id: int) -> bool:
    workout = get_workout(db, user_id, workout_id)
    if not workout:
        return False
    db.delete(workout)
    db.commit()
    return True


# ==================== 🔥 PRODUCTS (справочник КБЖУ) ====================

def search_products(db: Session, query: str, limit: int = 20) -> List[models.Product]:
    """Поиск продуктов по (части) названия для автодополнения при добавлении
    ингредиента. Запрос разбивается на слова, каждое слово должно входить
    в название — порядок слов не важен: «печенье овсяное» находит
    «овсяное печенье». При пустом запросе возвращаем продукты по алфавиту."""
    limit = max(1, min(limit, 50))
    q = (query or "").strip().lower()

    base = db.query(models.Product)

    if not q:
        return base.order_by(models.Product.name.asc()).limit(limit).all()

    words = q.split()
    for word in words:
        base = base.filter(models.Product.name.ilike(f"%{escape_like(word)}%", escape="\\"))
    # Кап на выборку: ранжируем в Python не более 300 кандидатов,
    # а не всю таблицу (она растёт со временем).
    matches = base.limit(300).all()

    # Ранжирование в Python: точное совпадение > совпадение фразы с начала
    # названия > все слова запроса совпадают с началами слов названия >
    # остальные; внутри групп — по длине названия и алфавиту (короче выше).
    def rank(p: models.Product):
        name = p.name.lower()
        name_words = name.split()
        if name == q:
            group = 0
        elif name.startswith(q):
            group = 1
        elif all(any(nw.startswith(w) for nw in name_words) for w in words):
            group = 2
        else:
            group = 3
        return (group, len(p.name), p.name)

    matches.sort(key=rank)
    return matches[:limit]


def get_product_sync(db: Session, product_id: int) -> Optional[models.Product]:
    return db.query(models.Product).filter(models.Product.id == product_id).first()


# ==================== MEALS ====================

# ==================== 🔥 SYNC FEEDBACK ====================



# ==================== 🔥 ОБУЧЕНИЕ ====================

def learn_products_from_feedback(db: Session, predicted: dict, corrected_food: str):
    """
    Обучаем KBJU базу на основе предсказания.

    ВНИМАНИЕ: сейчас НЕ вызывается из create_feedback_sync намеренно —
    функция записывает продукты с ВЫДУМАННЫМИ КБЖУ (100/5/5/10), что
    замусоривает справочник products и искажает расчёты calc_kbju.
    Прежде чем включать обратно, нужно брать реальные нутриенты.
    """

    if not predicted:
        return

    ingredients = predicted.get("ingredients", [])
    if not ingredients:
        return

    for ing in ingredients:
        name = normalize_name(ing.get("name", ""))

        if not name or len(name) < 3:
            continue

        exists = db.query(models.Product).filter(
            models.Product.name == name
        ).first()

        if exists:
            continue

        # грубая оценка (можно улучшить позже)
        weight = safe_float(ing.get("weight_g", 100), 100)

        from .protein_source import classify as classify_protein_type
        new_product = models.Product(
            name=name,
            calories=100,
            protein=5,
            fat=5,
            carbs=10,
            protein_type=classify_protein_type(name),
        )

        db.add(new_product)

    db.commit()


# ==================== FEEDBACK ====================

def create_feedback_sync(
    db: Session,
    task_id: str,
    image_path: str,
    corrected_food: str,
    corrected_weight: int,
    predicted_result: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None
) -> models.Feedback:

    feedback = models.Feedback(
        task_id=task_id,
        image_path=image_path,
        predicted_result=predicted_result,
        corrected_food=corrected_food,
        corrected_weight=corrected_weight,
        user_id=user_id,
        status=models.FeedbackStatus.PENDING
    )

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    # Ретрейн модели по накопленным фидбекам. ВАЖНО: без guard'а каждый
    # фидбек после десятого ставил бы в очередь НОВУЮ тяжёлую задачу
    # (pending_count не падает ниже 10, пока фидбеки не отмечены used) —
    # очередь Celery забивалась бы ретрейнами и анализ фото вставал.
    # Redis-флаг retrain:queued (SET NX + TTL) гарантирует максимум одну
    # задачу ретрейна в очереди/работе одновременно.
    try:
        pending_count = db.query(models.Feedback).filter(
            models.Feedback.status == models.FeedbackStatus.PENDING
        ).count()

        if pending_count >= 10:
            from .ml_service import get_redis_client
            acquired = get_redis_client().set(
                "retrain:queued", "1", nx=True, ex=3600
            )
            if acquired:
                logger.info(f"Triggering model retraining: {pending_count} pending feedbacks")
                from .tasks import retrain_model_task
                retrain_model_task.delay()
    except Exception as e:
        logger.warning(f"Retraining trigger failed: {e}")

    return feedback


def get_pending_feedback_sync(db: Session, limit: int = 100) -> List[models.Feedback]:
    return db.query(models.Feedback).filter(
        models.Feedback.status == models.FeedbackStatus.PENDING
    ).limit(limit).all()


def mark_feedback_used_sync(db: Session, feedback_ids: List[int]) -> None:
    db.query(models.Feedback).filter(
        models.Feedback.id.in_(feedback_ids)
    ).update(
        {models.Feedback.status: models.FeedbackStatus.USED},
        synchronize_session=False
    )
    db.commit()