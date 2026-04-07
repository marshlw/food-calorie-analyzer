import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException

from app.tasks import analyze_image_task
from celery.result import AsyncResult
from app.celery_app import celery_app

app = FastAPI()

# ✅ ЕДИНАЯ ПАПКА
UPLOAD_DIR = Path("/app/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health():
    return {"status": "ok"}


# --- ANALYZE ---
@app.post("/api/v1/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        file_id = f"{uuid.uuid4()}.jpg"
        file_path = UPLOAD_DIR / file_id

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        task = analyze_image_task.delay(str(file_path))

        return {"id": task.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- GET RESULT ---
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