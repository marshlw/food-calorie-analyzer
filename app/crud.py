# app/crud.py

from sqlalchemy.orm import selectinload, Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, date
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
    except:
        return default


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
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ==================== PROFILE / WEIGHT ====================

def compute_nutrition_targets(db: Session, user: models.User) -> Dict[str, Any]:
    """Единый расчёт суточных норм (BMR, калории, БЖУ, вода). Используется
    профилем, дневником, водой, советчиком и тренировками — цифры везде
    совпадают. Текущий вес берётся из последней записи истории.

    Ручные нормы пользователя (custom_* в профиле, важно для атлетов)
    имеют приоритет над авторасчётом — поэтому, заданные один раз,
    они автоматически подхватываются во всех формах."""
    from app import utils

    latest = get_latest_weight(db, user.id)
    weight = latest.weight_kg if latest else None
    age = utils.calc_age(user.birth_date)
    bmr = utils.calc_bmr(weight, user.height_cm, age, user.sex)
    calories = utils.calc_daily_calorie_target(bmr, user.activity_level)
    macros = utils.calc_macro_targets(calories)
    water_ml = utils.calc_water_target(weight, user.activity_level)

    # Переопределения из профиля (NULL/0 = использовать авторасчёт)
    if getattr(user, "custom_calorie_target", None):
        calories = user.custom_calorie_target
        # БЖУ по умолчанию следуют за ручной калорийностью…
        macros = utils.calc_macro_targets(calories)
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
        "calories": calories,
        "protein_g": protein_g,
        "protein_animal_g": protein_animal_g,
        "protein_plant_g": protein_plant_g,
        "fat_g": fat_g,
        "carbs_g": carbs_g,
        "water_ml": water_ml,
        "current_weight_kg": weight,
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


def update_profile(db: Session, user: models.User, payload: schemas.ProfileUpdate) -> models.User:
    # ВАЖНО: current_user приходит из сессии auth.get_current_user
    # (database.get_db), а эндпоинты работают через свою сессию (main.get_db).
    # Это РАЗНЫЕ сессии, поэтому коммит/refresh переданного объекта падает с
    # "not persistent within this Session". Перечитываем пользователя в
    # рабочей сессии db и мутируем уже его.
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
    for word in query.split():
        q = q.filter(models.Exercise.name.ilike(f"%{word}%"))
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
        base = base.filter(models.Product.name.ilike(f"%{word}%"))
    matches = base.all()

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
    Обучаем KBJU базу на основе предсказания
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

    # 🔥 ВАЖНО: обучаемся на основе исправления
    try:
        # Берём ингредиенты из предсказания если они есть, иначе создаём простой
        ingredients_to_learn = []
        
        if predicted_result and "ingredients" in predicted_result:
            ingredients_to_learn = predicted_result["ingredients"]
        else:
            # Fallback: один ингредиент - само блюдо
            ingredients_to_learn = [{
                "name": corrected_food,
                "weight_g": corrected_weight,
                "type": "carb"
            }]

        from .ml_service import learn_from_feedback
        learn_from_feedback(corrected_food, ingredients_to_learn)
        
    except Exception as e:
        logger.warning(f"Learning failed: {e}")

    # Проверяем, нужно ли retrain модель
    try:
        pending_count = db.query(models.Feedback).filter(
            models.Feedback.status == models.FeedbackStatus.PENDING
        ).count()

        if pending_count >= 10:  # retrain каждые 10 feedback
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