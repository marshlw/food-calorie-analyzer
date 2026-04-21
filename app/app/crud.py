# app/crud.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload, Session
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime
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

# ==================== ASYNC CRUD ====================

async def get_user_by_email(db: AsyncSession, email: str) -> Optional[models.User]:
    result = await db.execute(select(models.User).where(models.User.email == email))
    return result.scalar_one_or_none()


async def create_user(db: AsyncSession, user: schemas.UserCreate, hashed_password: str) -> models.User:
    db_user = models.User(
        email=user.email,
        full_name=user.full_name,
        hashed_password=hashed_password
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user


async def create_task(db: AsyncSession, user_id: int, image_hash: Optional[str] = None) -> models.Task:
    task_id = str(uuid.uuid4())
    task = models.Task(
        id=task_id,
        user_id=user_id,
        status=models.TaskStatus.PENDING,
        image_hash=image_hash
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task(db: AsyncSession, task_id: str) -> Optional[models.Task]:
    result = await db.execute(
        select(models.Task).where(models.Task.id == task_id)
    )
    return result.scalar_one_or_none()


async def update_task(
    db: AsyncSession,
    task_id: str,
    status: models.TaskStatus,
    result: Optional[dict] = None,
    error: Optional[str] = None
) -> Optional[models.Task]:

    task = await get_task(db, task_id)
    if not task:
        return None

    update_data = {
        "status": status,
        "updated_at": datetime.utcnow()
    }

    if result is not None:
        update_data["result_json"] = json.dumps(result, ensure_ascii=False)

    if error:
        update_data["error"] = error

    await db.execute(
        update(models.Task)
        .where(models.Task.id == task_id)
        .values(**update_data)
    )
    await db.commit()
    await db.refresh(task)

    return task


# ==================== MEALS ====================

async def create_meal(db: AsyncSession, meal: schemas.MealCreate, user_id: int) -> models.Meal:
    db_meal = models.Meal(
        user_id=user_id,
        meal_type=meal.meal_type,
        notes=meal.notes
    )
    db.add(db_meal)
    await db.commit()
    await db.refresh(db_meal)

    total_calories = 0
    total_protein = 0
    total_fat = 0
    total_carbs = 0

    for item in meal.items:
        db_item = models.MealItem(
            meal_id=db_meal.id,
            **item.dict()
        )
        db.add(db_item)

        total_calories += item.calories
        total_protein += item.protein_g
        total_fat += item.fat_g
        total_carbs += item.carbs_g

    db_meal.total_calories = total_calories
    db_meal.total_protein = total_protein
    db_meal.total_fat = total_fat
    db_meal.total_carbs = total_carbs

    await db.commit()
    await db.refresh(db_meal)

    return db_meal


async def get_user_meals(
    db: AsyncSession,
    user_id: int,
    limit: int = 50,
    offset: int = 0
) -> List[models.Meal]:

    result = await db.execute(
        select(models.Meal)
        .where(models.Meal.user_id == user_id)
        .options(selectinload(models.Meal.items))
        .order_by(models.Meal.date.desc())
        .limit(limit)
        .offset(offset)
    )
    return result.scalars().all()


# ==================== PHOTO ====================

async def create_photo(
    db: AsyncSession,
    meal_item_id: int,
    storage_path: str,
    thumbnail_path: Optional[str],
    file_hash: str,
    original_filename: Optional[str] = None,
    file_size: Optional[int] = None
) -> models.Photo:

    photo = models.Photo(
        meal_item_id=meal_item_id,
        storage_path=storage_path,
        thumbnail_path=thumbnail_path,
        file_hash=file_hash,
        original_filename=original_filename,
        file_size=file_size
    )
    db.add(photo)
    await db.commit()
    await db.refresh(photo)
    return photo


# ==================== 🔥 SYNC FEEDBACK ====================

def create_analysis_task_sync(db: Session, task_id: str, image_path: str) -> models.AnalysisTask:
    analysis_task = models.AnalysisTask(
        task_id=task_id,
        image_path=image_path
    )
    db.add(analysis_task)
    db.commit()
    db.refresh(analysis_task)
    return analysis_task


def get_analysis_task_sync(db: Session, task_id: str) -> Optional[models.AnalysisTask]:
    return db.query(models.AnalysisTask).filter(
        models.AnalysisTask.task_id == task_id
    ).first()


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

    # 🔥 ВАЖНО: обучаемся сразу
    try:
        learn_products_from_feedback(db, predicted_result, corrected_food)
    except Exception as e:
        logger.warning(f"Learning failed: {e}")

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