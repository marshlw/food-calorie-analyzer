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
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


# ==================== PROFILE / WEIGHT ====================

def compute_nutrition_targets(db: Session, user: models.User) -> Dict[str, Any]:
    """Единый расчёт суточных норм (BMR, калории, БЖУ) из веса/роста/возраста/
    активности. Используется и профилем, и дневником, чтобы цифры совпадали.
    Текущий вес берётся из последней записи истории."""
    from app import utils

    latest = get_latest_weight(db, user.id)
    weight = latest.weight_kg if latest else None
    age = utils.calc_age(user.birth_date)
    bmr = utils.calc_bmr(weight, user.height_cm, age, user.sex)
    calories = utils.calc_daily_calorie_target(bmr, user.activity_level)
    macros = utils.calc_macro_targets(calories)
    return {
        "bmr": bmr,
        "calories": calories,
        "protein_g": macros["protein_g"],
        "fat_g": macros["fat_g"],
        "carbs_g": macros["carbs_g"],
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


def upsert_weight_record(
    db: Session,
    user_id: int,
    weight_kg: float,
    recorded_on: Optional[date] = None,
    note: Optional[str] = None,
    source: str = "manual",
) -> models.WeightRecord:
    """Одна запись на (user, дата): повторное сохранение за тот же день
    обновляет существующую строку, а не создаёт дубль."""
    recorded_on = recorded_on or date.today()
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
    else:
        rec = models.WeightRecord(
            user_id=user_id,
            weight_kg=weight_kg,
            recorded_on=recorded_on,
            note=note,
            source=source,
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
    db.commit()

    # Вес из профиля -> в историю, только если изменился относительно
    # последнего значения (иначе незачем трогать запись за сегодня).
    if payload.weight_kg is not None and payload.save_weight_as_record:
        latest = get_latest_weight(db, db_user.id)
        if latest is None or latest.weight_kg != payload.weight_kg:
            upsert_weight_record(db, db_user.id, payload.weight_kg, source="profile_edit")

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


def add_meal_entry(db: Session, user_id: int, meal_data: schemas.MealEntryCreate, target_date: Optional[date] = None, task_id: Optional[str] = None) -> models.MealEntry:
    target_date = target_date or date.today()
    daily_log = get_or_create_daily_log(db, user_id, target_date)

    meal_entry = models.MealEntry(
        daily_log_id=daily_log.id,
        food_name=meal_data.food_name,
        calories=meal_data.calories,
        protein_g=meal_data.protein_g,
        fat_g=meal_data.fat_g,
        carbs_g=meal_data.carbs_g,
        weight_g=meal_data.weight_g,
        meal_type=getattr(meal_data, 'meal_type', 'snacks'),
        task_id=task_id
    )
    db.add(meal_entry)
    db.commit()
    db.refresh(meal_entry)
    return meal_entry


def get_daily_log(db: Session, user_id: int, date_value: date) -> Optional[models.DailyLog]:
    return db.query(models.DailyLog).options(selectinload(models.DailyLog.entries)).filter(
        models.DailyLog.user_id == user_id,
        models.DailyLog.date == date_value
    ).first()


def get_meal_entry_sync(db: Session, meal_entry_id: int) -> Optional[models.MealEntry]:
    return db.query(models.MealEntry).filter(models.MealEntry.id == meal_entry_id).first()


def calculate_daily_totals(log: models.DailyLog) -> Dict[str, float]:
    total_calories = 0.0
    total_protein = 0.0
    total_fat = 0.0
    total_carbs = 0.0

    for entry in log.entries:
        total_calories += entry.calories
        total_protein += entry.protein_g
        total_fat += entry.fat_g
        total_carbs += entry.carbs_g

    return {
        "total_calories": round(total_calories, 1),
        "total_protein": round(total_protein, 1),
        "total_fat": round(total_fat, 1),
        "total_carbs": round(total_carbs, 1)
    }


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

        new_product = models.Product(
            name=name,
            calories=100,
            protein=5,
            fat=5,
            carbs=10
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