# app/main.py

import uuid
import shutil
import os
import json
import logging
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal, engine
from app import models, schemas, crud, auth
from app.tasks import analyze_image_task

# Создаём таблицы
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

logger = logging.getLogger(__name__)

# CORS — для разработки разрешены все источники
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажи конкретные origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

UPLOAD_DIR = Path("/app/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ===================== DB =====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ===================== HEALTH =====================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ===================== ANALYZE (теперь требует аутентификации) =====================

@app.post("/api/v1/analyze")
async def analyze(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file_id = f"{uuid.uuid4()}.jpg"
    file_path = UPLOAD_DIR / file_id

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    task = None
    try:
        task = crud.create_task(db, current_user.id, str(file_path))
        analyze_image_task.delay(task.id, str(file_path))
        return {"id": task.id}
    except Exception as e:
        if task is not None:
            task.status = models.TaskStatus.FAILURE
            task.error = f"Enqueue failed: {e}"
            db.commit()
        raise HTTPException(status_code=500, detail="Unable to enqueue analysis task")


# ===================== REGISTER =====================

@app.post("/api/v1/register")
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email_sync(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = auth.get_password_hash(user.password)
    db_user = crud.create_user_sync(db, user, hashed_password)

    logger.info(f"User registered: {user.email}")
    return {"message": "Пользователь создан успешно"}


# ===================== LOGIN =====================

@app.post("/api/v1/login", response_model=schemas.Token)
async def login(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = auth.authenticate_user_sync(db, email, password)
    if not user:
        logger.warning(f"Failed login attempt for email: {email}")
        raise HTTPException(
            status_code=401,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": user.email})
    logger.info(f"User logged in: {email}")
    return {"access_token": access_token, "token_type": "bearer"}


# ===================== TOKEN (OAuth2 совместимость) =====================

@app.post("/api/v1/token", response_model=schemas.Token)
async def token(email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = auth.authenticate_user_sync(db, email, password)
    if not user:
        logger.warning(f"Failed token attempt for email: {email}")
        raise HTTPException(
            status_code=401,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}


# ===================== TASK STATUS =====================

@app.get("/api/v1/task/{task_id}")
async def get_task(task_id: str, db: Session = Depends(get_db)):
    task = crud.get_task_by_id_sync(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    result = None
    if task.result_json:
        try:
            result = json.loads(task.result_json)
        except Exception:
            result = None

    return {
        "id": task.id,
        "status": task.status.value,
        "result": result,
        "error": task.error,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


# ===================== USER TASKS HISTORY =====================

@app.get("/api/v1/tasks")
async def get_user_tasks(
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    tasks = crud.get_tasks_by_user_sync(db, current_user.id, limit, offset)
    return [
        {
            "id": task.id,
            "status": task.status.value,
            "result": json.loads(task.result_json) if task.result_json else None,
            "error": task.error,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat() if task.updated_at else None
        }
        for task in tasks
    ]


@app.post("/api/v1/meals", response_model=schemas.MealEntryResponse)
async def add_meal(
    meal: schemas.MealEntryCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Adding meal for user {current_user.id}: {meal.food_name}, type={meal.meal_type}")
        return crud.add_meal_entry(db, current_user.id, meal)
    except Exception as e:
        logger.error(f"Error adding meal: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/daily-log", response_model=schemas.DailyLogResponse)
async def get_daily_log(
    date_str: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        date_value = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")

    log = crud.get_daily_log(db, current_user.id, date_value)
    if not log:
        return {
            "date": date_value,
            "total_calories": 0.0,
            "total_protein": 0.0,
            "total_fat": 0.0,
            "total_carbs": 0.0,
            "meals": []
        }

    totals = crud.calculate_daily_totals(log)
    return {
        "date": log.date,
        **totals,
        "meals": log.entries
    }


@app.post("/api/v1/meals/from-analysis", response_model=schemas.MealEntryResponse)
async def add_meal_from_analysis(
    payload: schemas.AnalysisMealRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = crud.get_task_by_id_sync(db, payload.task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    if task.status != models.TaskStatus.SUCCESS:
        raise HTTPException(status_code=400, detail="Analysis task is not successful")

    if not task.result_json:
        raise HTTPException(status_code=400, detail="Analysis result is missing")

    try:
        result_data = json.loads(task.result_json)
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to parse analysis result")

    meal_data = schemas.MealEntryCreate(
        food_name=result_data.get("food") or result_data.get("food_name") or "analyzed meal",
        calories=result_data.get("calories", 0),
        protein_g=result_data.get("protein_g", 0),
        fat_g=result_data.get("fat_g", 0),
        carbs_g=result_data.get("carbs_g", 0),
        weight_g=result_data.get("weight_g", 0),
        meal_type=payload.meal_type
    )


@app.post("/api/v1/feedback", response_model=schemas.FeedbackResponse)
async def submit_feedback(
    feedback: schemas.FeedbackRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Проверяем, что задача принадлежит пользователю
        task = crud.get_task_by_id_sync(db, feedback.task_id)
        if not task or task.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Task not found")

        # Сохраняем фидбек
        feedback_obj = crud.create_feedback_sync(
            db,
            task_id=feedback.task_id,
            user_id=current_user.id,
            corrected_food=feedback.correct_food,
            corrected_weight=feedback.correct_weight
        )

        return schemas.FeedbackResponse(
            status="success",
            id=feedback_obj.id
        )

    except Exception as e:
        logger.error(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    try:
        return crud.add_meal_entry(db, current_user.id, meal_data, task_id=task.id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/v1/meals/{meal_id}", response_model=schemas.MealEntryResponse)
async def edit_meal_entry(
    meal_id: int,
    update: schemas.MealEntryCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    meal_entry = crud.get_meal_entry_sync(db, meal_id)
    if not meal_entry or meal_entry.daily_log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Meal entry not found")

    meal_entry.food_name = update.food_name
    meal_entry.calories = update.calories
    meal_entry.protein_g = update.protein_g
    meal_entry.fat_g = update.fat_g
    meal_entry.carbs_g = update.carbs_g
    meal_entry.weight_g = update.weight_g
    meal_entry.meal_type = getattr(update, 'meal_type', meal_entry.meal_type)

    db.commit()
    db.refresh(meal_entry)
    return meal_entry


@app.delete("/api/v1/meals/{meal_id}")
async def delete_meal_entry(
    meal_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    meal_entry = crud.get_meal_entry_sync(db, meal_id)
    if not meal_entry or meal_entry.daily_log.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Meal entry not found")

    db.delete(meal_entry)
    db.commit()
    return {"status": "ok", "deleted_id": meal_id}


# ===================== FEEDBACK =====================

@app.post("/api/v1/feedback", response_model=schemas.FeedbackResponse)
async def save_feedback(
    feedback: schemas.FeedbackRequest,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = crud.get_task_by_id_sync(db, feedback.task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")

    predicted = None
    if task.status == models.TaskStatus.SUCCESS and task.result_json:
        try:
            predicted = json.loads(task.result_json)
        except Exception:
            predicted = None

    fb_record = crud.create_feedback_sync(
        db=db,
        task_id=feedback.task_id,
        image_path=task.image_path,
        corrected_food=feedback.correct_food,
        corrected_weight=feedback.correct_weight,
        predicted_result=predicted,
        user_id=current_user.id
    )

    return {"status": "ok", "id": fb_record.id}


# ==================== ADMIN ====================

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "change-me-in-production")


@app.get("/api/v1/admin/feedback", response_model=List[schemas.FeedbackListItem])
async def list_feedback(
    limit: int = 100,
    offset: int = 0,
    status: Optional[str] = None,
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    db = SessionLocal()
    try:
        query = db.query(models.Feedback)
        if status:
            try:
                fb_status = models.FeedbackStatus(status)
                query = query.filter(models.Feedback.status == fb_status)
            except ValueError:
                pass

        feedbacks = (
            query
            .order_by(models.Feedback.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return feedbacks
    finally:
        db.close()


@app.get("/api/v1/admin/feedback/{feedback_id}", response_model=schemas.FeedbackListItem)
async def get_feedback(
    feedback_id: int,
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    db = SessionLocal()
    try:
        fb = db.query(models.Feedback).filter(models.Feedback.id == feedback_id).first()
        if not fb:
            raise HTTPException(status_code=404, detail="Feedback not found")
        return fb
    finally:
        db.close()


@app.patch("/api/v1/admin/feedback/{feedback_id}/status")
async def update_feedback_status(
    feedback_id: int,
    status: str,
    x_admin_token: str = Header(..., alias="X-Admin-Token")
):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")

    try:
        fb_status = models.FeedbackStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status")

    db = SessionLocal()
    try:
        fb = db.query(models.Feedback).filter(models.Feedback.id == feedback_id).first()
        if not fb:
            raise HTTPException(status_code=404, detail="Feedback not found")

        fb.status = fb_status
        db.commit()
        return {"status": "ok", "id": feedback_id, "new_status": status}
    finally:
        db.close()