# app/main.py
import uuid
import shutil
import os                     # <-- добавлено
from pathlib import Path
from typing import List, Optional  # <-- добавлено

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header  # <-- Header добавлен
from sqlalchemy.orm import Session
from celery.result import AsyncResult

from app.celery_app import celery_app
from app.database import SessionLocal, engine
from app import models, schemas, crud
from app.tasks import analyze_image_task
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

        # Сохраняем связку task_id → image_path для будущего фидбека
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
    analysis_task = crud.get_analysis_task_sync(db, feedback.task_id)
    if not analysis_task:
        raise HTTPException(status_code=404, detail="Task not found")

    task_result = AsyncResult(feedback.task_id, app=celery_app)
    predicted = None
    if task_result.successful():
        predicted = task_result.result

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


# ==================== АДМИНСКИЕ ЭНДПОИНТЫ ====================
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
        feedbacks = query.order_by(models.Feedback.created_at.desc()).offset(offset).limit(limit).all()
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
        raise HTTPException(status_code=400, detail="Invalid status. Use 'pending' or 'used'.")

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