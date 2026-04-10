# app/main.py
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.database import SessionLocal, engine
from app import models, schemas, crud
from app.tasks import analyze_image_task  # ✅ добавлен импорт задачи

# Создаём таблицы при старте (если ещё не созданы)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

UPLOAD_DIR = Path("/app/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# Dependency для получения синхронной сессии БД
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/v1/analyze")
async def analyze(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        file_id = f"{uuid.uuid4()}.jpg"
        file_path = UPLOAD_DIR / file_id

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = analyze_image_task.delay(str(file_path))

        # ✅ Сохраняем связку task_id → image_path для будущего фидбека
        crud.create_analysis_task_sync(db, task.id, str(file_path))

        return {"id": task.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/task/{task_id}")
async def get_task(task_id: str):
    task = AsyncResult(task_id, app=celery_app)

    if task.state == "PENDING":
        return {"status": "pending"}

    if task.state == "FAILURE":
        return {"status": "error"}

    if task.state == "SUCCESS":
        return {
            "status": "success",
            "result": task.result
        }

    return {"status": task.state}


@app.post("/api/v1/feedback", response_model=schemas.FeedbackResponse)
async def save_feedback(feedback: schemas.FeedbackRequest, db: Session = Depends(get_db)):
    # Находим запись об анализе по task_id
    analysis_task = crud.get_analysis_task_sync(db, feedback.task_id)
    if not analysis_task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Пытаемся получить результат предсказания из Celery (если он ещё жив)
    task_result = AsyncResult(feedback.task_id, app=celery_app)
    predicted = None
    if task_result.successful():
        predicted = task_result.result

    # Сохраняем фидбек (используем синхронную функцию с правильной сигнатурой)
    fb_record = crud.create_feedback_sync(
        db=db,
        task_id=feedback.task_id,
        image_path=analysis_task.image_path,
        corrected_food=feedback.correct_food,
        corrected_weight=feedback.correct_weight,
        predicted_result=predicted,
        user_id=feedback.user_id
    )
    return {"status": "ok", "id": fb_record.id}