# app/main.py

import os
import time
import uuid
import shutil
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime, date
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Request, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image
from sqlalchemy.orm import Session

from app.config import settings
from app.celery_app import celery_app
from app.database import SessionLocal, engine
from app import models, schemas, crud, auth, ml_service, utils
from app.tasks import analyze_image_task

app = FastAPI()
logger = logging.getLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    elapsed = round(time.time() - start_time, 3)
    logger.info(
        "HTTP request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration": elapsed,
        },
    )
    return response


@app.exception_handler(Exception)
async def internal_server_error(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


@app.on_event("startup")
async def startup_event():
    try:
        # ensure_schema() = create_all() + добор недостающих колонок профиля
        # в существующей таблице users (create_all сам колонки не добавляет).
        from app.database import ensure_schema
        ensure_schema()
        logger.info("Database schema checked/created")
    except Exception as exc:
        logger.warning("Database schema creation failed", exc_info=exc)

    # Засев справочника продуктов (КБЖУ на 100 г), идемпотентно
    try:
        from .seed_products import seed_products
        session = SessionLocal()
        try:
            seed_products(session)
        finally:
            session.close()
    except Exception as exc:
        logger.warning("Product seeding failed", exc_info=exc)

    try:
        ml_service.get_http_client()
        ml_service.get_redis_client()
        logger.info("Startup complete: external resources initialized")
    except Exception as exc:
        logger.warning("Startup resource initialization failed", exc_info=exc)


@app.on_event("shutdown")
async def shutdown_event():
    try:
        ml_service.close_http_client()
        ml_service.close_redis_client()
        logger.info("Shutdown complete: external resources closed")
    except Exception as exc:
        logger.warning("Shutdown cleanup failed", exc_info=exc)


def _validate_uploaded_image(path: Path) -> None:
    try:
        with Image.open(path) as img:
            img.verify()
            if not img.format or img.format.upper() not in ALLOWED_IMAGE_FORMATS:
                raise ValueError("Unsupported image format")
    except Exception as exc:
        logger.warning("Invalid upload image", extra={"path": str(path), "error": str(exc)})
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from exc


def _save_upload_file_securely(upload_file: UploadFile) -> Path:
    filename = upload_file.filename or ""
    extension = Path(filename).suffix.lower()
    if extension not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_file.file.seek(0)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=str(UPLOAD_DIR)) as tmp:
            temp_path = Path(tmp.name)
            total_bytes = 0
            while True:
                chunk = upload_file.file.read(8192)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_UPLOAD_SIZE:
                    raise HTTPException(status_code=413, detail="Uploaded file is too large")
                tmp.write(chunk)

        _validate_uploaded_image(temp_path)

        target_path = UPLOAD_DIR / f"{uuid.uuid4()}{extension}"
        os.replace(str(temp_path), str(target_path))
        return target_path
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Upload save failed", extra={"filename": filename, "error": str(exc)})
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid image") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


# ===================== DB =====================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _get_auth_request(request: Request) -> schemas.AuthRequest:
    try:
        content_type = request.headers.get("content-type", "")
        logger.debug(f"Auth request content-type: {content_type}")
        
        if content_type.startswith("application/json"):
            body = await request.json()
        else:
            # Try form data fallback
            try:
                body = dict(await request.form())
            except Exception:
                # If form parsing fails, try JSON anyway
                body = await request.json()
        
        logger.debug(f"Auth request body: {body}")
        auth_request = schemas.AuthRequest(**body)
        return auth_request
    except Exception as e:
        logger.error(f"Error parsing auth request: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid request format: {str(e)}")


# ===================== HEALTH =====================

@app.get("/health")
async def health():
    return {"status": "ok"}


# ===================== ANALYZE (теперь требует аутентификации) =====================

@app.post("/api/v1/analyze", response_model=schemas.TaskCreatedResponse, status_code=status.HTTP_201_CREATED)
async def analyze(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    file_path = _save_upload_file_securely(file)
    logger.info("File uploaded securely", extra={"user_id": current_user.id, "path": str(file_path)})

    task = None
    try:
        task = crud.create_task(db, current_user.id, str(file_path))
        analyze_image_task.delay(task.id, str(file_path))
        return {"id": task.id, "status": task.status.value}
    except Exception as e:
        if task is not None:
            task.status = models.TaskStatus.FAILURE
            task.error = f"Enqueue failed: {e}"
            db.commit()
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError:
                logger.warning("Unable to remove uploaded file after enqueue failure", extra={"path": str(file_path)})
        logger.exception("Unable to enqueue analysis task")
        raise HTTPException(status_code=500, detail="Unable to enqueue analysis task")


# ===================== REGISTER =====================

@app.post("/api/v1/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email_sync(db, user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Пользователь уже существует")

    hashed_password = auth.get_password_hash(user.password)
    db_user = crud.create_user_sync(db, user, hashed_password)

    # UX из ТЗ: вес, заполненный при регистрации, становится первой
    # записью в истории взвешиваний.
    if user.weight_kg:
        try:
            crud.upsert_weight_record(db, db_user.id, user.weight_kg, source="registration")
        except Exception as exc:
            logger.warning("Failed to seed initial weight record", exc_info=exc)

    logger.info(f"User registered: {user.email}")
    return db_user


# ===================== LOGIN =====================

@app.post("/api/v1/login", response_model=schemas.Token)
async def login(auth_data: schemas.AuthRequest = Depends(_get_auth_request), db: Session = Depends(get_db)):
    if auth_data.grant_type != "password":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    user = auth.authenticate_user_sync(db, auth_data.email, auth_data.password)
    if not user:
        logger.warning(f"Failed login attempt for email: {auth_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "access_token": auth.create_access_token(data={"sub": user.email}),
        "refresh_token": auth.create_refresh_token(data={"sub": user.email}),
        "token_type": "bearer",
    }


# ===================== TOKEN (OAuth2 совместимость) =====================

@app.post("/api/v1/token", response_model=schemas.Token)
async def token(auth_data: schemas.AuthRequest = Depends(_get_auth_request), db: Session = Depends(get_db)):
    if auth_data.grant_type == "refresh_token":
        if not auth_data.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token is required")

        email = auth.verify_refresh_token(auth_data.refresh_token)
        user = crud.get_user_by_email_sync(db, email)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
        return {
            "access_token": auth.create_access_token(data={"sub": user.email}),
            "refresh_token": auth.create_refresh_token(data={"sub": user.email}),
            "token_type": "bearer",
        }

    if auth_data.grant_type != "password":
        raise HTTPException(status_code=400, detail="Unsupported grant_type")

    user = auth.authenticate_user_sync(db, auth_data.email, auth_data.password)
    if not user:
        logger.warning(f"Failed token attempt for email: {auth_data.email}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": auth.create_access_token(data={"sub": user.email}),
        "refresh_token": auth.create_refresh_token(data={"sub": user.email}),
        "token_type": "bearer",
    }


@app.get("/api/v1/me", response_model=schemas.User)
async def get_me(current_user: models.User = Depends(auth.get_current_user)):
    return current_user


# ===================== PROFILE =====================

def _build_profile(db: Session, user: models.User) -> dict:
    """Собирает ProfileResponse: текущий вес = последняя запись истории,
    плюс производные BMR и суточные нормы КБЖУ."""
    # Для графика на профиле достаточно последних ~30 записей.
    recent = crud.list_weight_history(db, user.id)[-30:]
    t = crud.compute_nutrition_targets(db, user)

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "height_cm": user.height_cm,
        "current_weight_kg": t["current_weight_kg"],
        "sex": user.sex,
        "birth_date": user.birth_date,
        "activity_level": user.activity_level,
        "recent_weights": recent,
        "bmr": t["bmr"],
        "daily_calorie_target": t["calories"],
        "protein_target_g": t["protein_g"],
        "fat_target_g": t["fat_g"],
        "carbs_target_g": t["carbs_g"],
        "water_target_ml": t["water_ml"],
    }


@app.get("/api/v1/profile", response_model=schemas.ProfileResponse)
async def get_profile(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return _build_profile(db, current_user)


@app.put("/api/v1/profile", response_model=schemas.ProfileResponse)
async def update_profile(
    payload: schemas.ProfileUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    user = crud.update_profile(db, current_user, payload)
    return _build_profile(db, user)


@app.post(
    "/api/v1/profile/weight",
    response_model=schemas.WeightRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_weight_record(
    payload: schemas.WeightRecordCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if payload.recorded_on and payload.recorded_on > date.today():
        raise HTTPException(status_code=400, detail="Дата записи не может быть в будущем")
    return crud.upsert_weight_record(
        db, current_user.id, payload.weight_kg,
        recorded_on=payload.recorded_on, note=payload.note, source="manual",
    )


@app.get(
    "/api/v1/profile/weight-history",
    response_model=List[schemas.WeightRecordResponse],
)
async def get_weight_history(
    start: Optional[date] = None,
    end: Optional[date] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return crud.list_weight_history(db, current_user.id, start, end)


# ===================== TASK STATUS =====================

@app.get("/api/v1/task/{task_id}", response_model=schemas.TaskResponse)
async def get_task(
    task_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    task = crud.get_task_by_id_sync(db, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


# ===================== USER TASKS HISTORY =====================

@app.get("/api/v1/tasks", response_model=List[schemas.TaskResponse])
async def get_user_tasks(
    limit: int = 50,
    offset: int = 0,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return crud.get_tasks_by_user_sync(db, current_user.id, limit, offset)


@app.post("/api/v1/meals", response_model=schemas.MealEntryResponse, status_code=status.HTTP_201_CREATED)
async def add_meal(
    meal: schemas.MealEntryCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    try:
        logger.info(f"Adding meal for user {current_user.id}: {meal.food_name}, type={meal.meal_type}")
        return crud.add_meal_entry(db, current_user.id, meal, target_date=meal.date, task_id=meal.task_id)
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

    # Суточные нормы КБЖУ пользователя — одни и те же для любого дня.
    targets = crud.compute_nutrition_targets(db, current_user)
    targets_payload = {
        "calories": targets["calories"],
        "protein_g": targets["protein_g"],
        "fat_g": targets["fat_g"],
        "carbs_g": targets["carbs_g"],
    }

    # Вода за этот день (для кольца-инфографики). Норма — из тех же расчётов.
    water_payload = {
        "date": date_value,
        "total_ml": crud.get_water_total(db, current_user.id, date_value),
        "goal_ml": targets["water_ml"],
        "glass_ml": utils.GLASS_ML,
    }

    log = crud.get_daily_log(db, current_user.id, date_value)
    if not log:
        return {
            "date": date_value,
            "total_calories": 0.0,
            "total_protein": 0.0,
            "total_fat": 0.0,
            "total_carbs": 0.0,
            "meals": [],
            "targets": targets_payload,
            "water": water_payload,
        }

    totals = crud.calculate_daily_totals(log)
    return {
        "date": log.date,
        **totals,
        "meals": log.entries,
        "targets": targets_payload,
        "water": water_payload,
    }


# ===================== WATER =====================

def _build_water_payload(db: Session, user: models.User, date_value: date) -> dict:
    """Состояние воды за день: выпито + норма (из тех же расчётов, что КБЖУ)."""
    targets = crud.compute_nutrition_targets(db, user)
    return {
        "date": date_value,
        "total_ml": crud.get_water_total(db, user.id, date_value),
        "goal_ml": targets["water_ml"],
        "glass_ml": utils.GLASS_ML,
    }


@app.get("/api/v1/water", response_model=schemas.WaterResponse)
async def get_water(
    date_str: Optional[str] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    try:
        date_value = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format, expected YYYY-MM-DD")
    return _build_water_payload(db, current_user, date_value)


@app.post("/api/v1/water", response_model=schemas.WaterResponse)
async def update_water(
    payload: schemas.WaterUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    date_value = payload.date or date.today()
    if date_value > date.today():
        raise HTTPException(status_code=400, detail="Дата не может быть в будущем")
    # По умолчанию — добавить один стакан.
    amount = payload.amount_ml if payload.amount_ml is not None else utils.GLASS_ML
    crud.adjust_water(db, current_user.id, amount, date_value=date_value)
    return _build_water_payload(db, current_user, date_value)


@app.post("/api/v1/meals/from-analysis", response_model=schemas.MealEntryResponse, status_code=status.HTTP_201_CREATED)
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
        calories=float(result_data.get("calories", 0)),
        protein_g=float(result_data.get("protein_g", 0)),
        fat_g=float(result_data.get("fat_g", 0)),
        carbs_g=float(result_data.get("carbs_g", 0)),
        weight_g=float(result_data.get("weight_g", 0)),
        meal_type=payload.meal_type
    )

    try:
        return crud.add_meal_entry(db, current_user.id, meal_data, task_id=task.id)
    except Exception as e:
        logger.error(f"Error creating meal from analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/feedback", response_model=schemas.FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def submit_feedback(
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

    return schemas.FeedbackResponse(status="success", id=fb_record.id)


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


# ==================== UPLOADS ====================

# Раздаём загруженные изображения, чтобы фронтенд мог показывать превью
# (TaskResponse.image_path возвращает путь вида /uploads/<filename>)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


# ==================== FRONTEND ====================

from starlette.exceptions import HTTPException as StarletteHTTPException


class SPAStaticFiles(StaticFiles):
    """StaticFiles с SPA-fallback: для неизвестного не-API пути отдаём index.html,
    чтобы клиентские маршруты React Router (/meals, /profile, ...) открывались
    и при прямом заходе/перезагрузке, а не только при переходе внутри приложения."""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            # API-маршруты должны и дальше отдавать честный 404 (JSON), не index.html
            if exc.status_code == 404 and not path.startswith("api"):
                return await super().get_response("index.html", scope)
            raise


# Serve static files (frontend)
FRONTEND_DIR = Path(__file__).parent / "static" / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
else:
    logger.warning(f"Frontend directory not found: {FRONTEND_DIR}")
