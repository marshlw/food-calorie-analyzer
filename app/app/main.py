from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
import os
import uuid
import json
from pathlib import Path
import shutil
import logging
from datetime import datetime
from . import models
from .config import settings
from .database import get_db, init_db
from . import crud, schemas, auth, ml_service
from .utils import process_image, compute_file_hash, validate_image_file

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Food Calorie Analyzer API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Обработчики событий
@app.on_event("startup")
async def startup_event():
    await init_db()
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    logger.info("Application started")

@app.on_event("shutdown")
async def shutdown_event():
    from .database import close_db
    await close_db()
    logger.info("Application shutdown")

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

# Аутентификация
@app.post("/api/v1/register", response_model=schemas.User)
async def register(
    user: schemas.UserCreate,
    db = Depends(get_db)
):
    db_user = await crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    hashed_password = auth.get_password_hash(user.password)
    new_user = await crud.create_user(db, user, hashed_password)
    return new_user

@app.post("/api/v1/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db = Depends(get_db)
):
    user = await auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = auth.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/api/v1/users/me", response_model=schemas.User)
async def read_users_me(current_user = Depends(auth.get_current_user)):
    # Явно преобразуем SQLAlchemy модель в Pydantic (если нужно)
    return schemas.User(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        created_at=current_user.created_at
    )

# Основной эндпоинт анализа
@app.post("/api/v1/analyze", response_model=schemas.TaskResponse)
async def analyze_photo(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user = Depends(auth.get_current_user),
    db = Depends(get_db)
):
    # Валидация файла
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image files are allowed"
        )

    # Проверка расширения
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    # Генерация уникального имени файла
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = Path(settings.UPLOAD_DIR) / unique_filename

    try:
        # Сохраняем оригинальный файл
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Проверка размера
        file_size = file_path.stat().st_size
        if file_size > settings.MAX_UPLOAD_SIZE:
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB"
            )

        # Валидация что это действительно изображение
        if not validate_image_file(str(file_path)):
            file_path.unlink(missing_ok=True)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid image file"
            )

        # Обработка изображения (сжатие, ресайз, удаление EXIF)
        processed_path = process_image(
            str(file_path),
            max_size=(settings.MAX_IMAGE_SIZE, settings.MAX_IMAGE_SIZE),
            quality=settings.IMAGE_QUALITY
        )

        # Вычисляем хэш обработанного файла
        file_hash = compute_file_hash(processed_path)

        # Проверяем кэш в Redis (если подключен)
        try:
            import redis.asyncio as redis
            redis_client = redis.from_url(settings.REDIS_URL)
            cached = await redis_client.get(f"analysis:{file_hash}")
            if cached:
                cached_result = json.loads(cached)
                # Создаем задачу с готовым результатом
                task = await crud.create_task(db, current_user.id, file_hash)
                await crud.update_task(
                    db,
                    task.id,
                    models.TaskStatus.SUCCESS,
                    result=cached_result
                )
                return schemas.TaskResponse(
                    id=task.id,
                    status="success",
                    result=cached_result,
                    created_at=task.created_at,
                    updated_at=task.updated_at
                )
        except:
            pass  # Если Redis недоступен, продолжаем

        # Создаем задачу в БД
        task = await crud.create_task(db, current_user.id, file_hash)

        # Запускаем фоновую задачу
        background_tasks.add_task(
            process_analysis_task,
            task_id=task.id,
            user_id=current_user.id,
            image_path=processed_path,
            file_hash=file_hash,
            db=db
        )

        return schemas.TaskResponse(
            id=task.id,
            status="pending",
            created_at=task.created_at
        )

    except Exception as e:
        logger.error(f"Upload failed: {str(e)}", exc_info=True)  # exc_info добавит traceback
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {str(e)}"
        )

@app.get("/api/v1/task/{task_id}", response_model=schemas.TaskResponse)
async def get_task_status(
    task_id: str,
    db = Depends(get_db),
    current_user = Depends(auth.get_current_user)
):
    task = await crud.get_task(db, task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )

    result = None
    if task.result_json:
        try:
            result = json.loads(task.result_json)
        except:
            result = None

    return schemas.TaskResponse(
        id=task.id,
        status=task.status.value,
        result=result,
        error=task.error,
        created_at=task.created_at,
        updated_at=task.updated_at
    )

@app.post("/api/v1/meals", response_model=schemas.Meal)
async def create_meal(
    meal: schemas.MealCreate,
    task_id: Optional[str] = None,
    db = Depends(get_db),
    current_user = Depends(auth.get_current_user)
):
    """
    Создает прием пищи. Можно передать task_id для автоматического создания
    MealItem из результата анализа.
    """
    if task_id:
        task = await crud.get_task(db, task_id)
        if not task or task.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task not found"
            )
        if task.status != models.TaskStatus.SUCCESS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task not completed successfully"
            )

        result = json.loads(task.result_json) if task.result_json else None
        if result:
            meal.items.append(
                schemas.MealItemCreate(
                    food_name=result["food"],
                    quantity_g=result["weight_g"],
                    calories=result["calories"],
                    protein_g=result["protein_g"],
                    fat_g=result["fat_g"],
                    carbs_g=result["carbs_g"],
                    source="ml",
                    confidence=result.get("confidence"),
                    note=result.get("note")
                )
            )

    return await crud.create_meal(db, meal, current_user.id)

@app.get("/api/v1/meals", response_model=List[schemas.Meal])
async def read_meals(
    limit: int = 50,
    offset: int = 0,
    db = Depends(get_db),
    current_user = Depends(auth.get_current_user)
):
    meals = await crud.get_user_meals(db, current_user.id, limit, offset)
    return meals

# Фоновая задача обработки
async def process_analysis_task(
    task_id: str,
    user_id: int,
    image_path: str,
    file_hash: str,
    db: AsyncSession
):
    try:
        await crud.update_task(db, task_id, models.TaskStatus.PROCESSING)
        result = await ml_service.analyze_image_async(image_path)

        # Кэшируем результат
        try:
            import redis.asyncio as redis
            redis_client = redis.from_url(settings.REDIS_URL)
            await redis_client.setex(
                f"analysis:{file_hash}",
                settings.CACHE_TTL,
                json.dumps(result, ensure_ascii=False)
            )
        except:
            pass

        await crud.update_task(
            db,
            task_id,
            models.TaskStatus.SUCCESS,
            result=result
        )
        logging.info(f"Task {task_id} completed successfully")

    except Exception as e:
        logging.error(f"Task {task_id} failed: {str(e)}")
        await crud.update_task(
            db,
            task_id,
            models.TaskStatus.FAILURE,
            error=str(e)
        )
    finally:
        try:
            Path(image_path).unlink(missing_ok=True)
        except:
            pass