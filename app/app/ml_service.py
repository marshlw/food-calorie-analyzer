import asyncio
import json
import logging
import re
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

import ollama
import redis
import cv2
from PIL import Image

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings
from . import models

# ================= LOGGING =================

logger = logging.getLogger(__name__)

# ================= INIT =================

client = ollama.Client(host=settings.OLLAMA_HOST)

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True,
    socket_timeout=2,
    socket_connect_timeout=2,
    retry_on_timeout=True
)

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=5,
    max_overflow=10
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

UPLOAD_DIR = Path(settings.UPLOAD_DIR)


# ================= DB =================

def get_product(session, name: str):
    try:
        return session.query(models.Product).filter(
            models.Product.name == name.lower()
        ).first()
    except Exception as e:
        logger.warning(f"DB error: {e}")
        return None


# ================= JSON SAFETY =================

def extract_json(text: str) -> Optional[dict]:
    if not text:
        return None

    # убрать markdown ```json
    text = text.strip()
    text = re.sub(r"^```json|```$", "", text, flags=re.MULTILINE).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    # fallback: вытаскиваем первый JSON блок
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass

    logger.warning(f"Invalid LLM JSON: {text[:300]}")
    return None


# ================= MODEL =================

def call_model(prompt: str, image: str | None = None) -> Optional[dict]:
    try:
        msg = {"role": "user", "content": prompt}
        if image:
            msg["images"] = [image]

        res = client.chat(
            model=settings.MODEL_NAME,
            messages=[msg],
            options={
                "temperature": 0.1,
                "top_p": 0.9
            }
        )

        return extract_json(res.get("message", {}).get("content"))

    except Exception as e:
        logger.error(f"Ollama error: {e}")
        return None


# ================= PROMPTS =================

PROMPT = """
Ты анализируешь еду по изображению.

Верни СТРОГО JSON:

{
 "food": "название блюда",
 "ingredients": [{"name": "ингредиент"}],
 "confidence": 0.0
}

Правила:
- только реальные ингредиенты
- не добавляй лишнего
- если не уверен — ставь низкую confidence
"""

PROMPT_WEIGHT = """
Оцени вес еды на фото.

Верни JSON:
{"weight_g": число}
"""


# ================= IMAGE =================

def preprocess(path: str) -> str:
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((1024, 1024))

        out = UPLOAD_DIR / f"p_{Path(path).name}"
        img.save(out, format="JPEG", quality=85)

        return str(out)

    except Exception as e:
        logger.warning(f"Image preprocess error: {e}")
        return path


def get_hash(path: str) -> str:
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except Exception:
        return "nohash"
    return h.hexdigest()


# ================= CV =================

def estimate_weight_cv(image_path: str) -> int:
    try:
        img = cv2.imread(image_path)
        if img is None:
            return 250

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 120, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(
            thresh,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )

        if not contours:
            return 250

        area = max(cv2.contourArea(c) for c in contours)
        ratio = area / (img.shape[0] * img.shape[1])

        return int(max(120, min(100 + ratio * 700, 800)))

    except Exception as e:
        logger.warning(f"CV error: {e}")
        return 250


def estimate_weight_llm(image: str) -> int:
    r = call_model(PROMPT_WEIGHT, image)
    if not r:
        return 250

    try:
        w = int(r.get("weight_g", 250))
    except Exception:
        w = 250

    return max(120, min(w, 800))


def combine_weights(cv_w: int, llm_w: int) -> int:
    return int(0.4 * cv_w + 0.6 * llm_w)


# ================= KBJU =================

def calc_kbju(session, ingredients: List[dict]) -> Dict[str, float]:
    total = {
        "calories": 0.0,
        "protein_g": 0.0,
        "fat_g": 0.0,
        "carbs_g": 0.0,
        "weight_g": 0.0
    }

    for ing in ingredients:
        name = ing.get("name", "").lower()
        product = get_product(session, name)

        if not product:
            continue

        w = ing.get("weight_g", 0)
        k = w / 100

        total["weight_g"] += w
        total["calories"] += product.calories * k
        total["protein_g"] += product.protein * k
        total["fat_g"] += product.fat * k
        total["carbs_g"] += product.carbs * k

    if total["weight_g"] == 0:
        total["weight_g"] = 200

    return {k: round(v, 1) for k, v in total.items()}


# ================= MAIN =================

def analyze_image_sync(path: str) -> dict:
    fallback = {
        "food": "не распознано",
        "weight_g": 200,
        "calories": 200,
        "protein_g": 10,
        "fat_g": 10,
        "carbs_g": 20,
        "confidence": 0.0,
        "ingredients": [],
        "source": "fallback"
    }

    session = SessionLocal()

    try:
        cache_key = f"final:{get_hash(path)}"

        try:
            cached = redis_client.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

        img = preprocess(path)

        data = call_model(PROMPT, img)
        if not data:
            return fallback

        ingredients = (data.get("ingredients") or [])[:4]
        if not ingredients:
            return fallback

        cv_w = estimate_weight_cv(img)
        llm_w = estimate_weight_llm(img)

        total_weight = max(150, combine_weights(cv_w, llm_w))

        # safe distribution
        if len(ingredients) > 0:
            per = int(total_weight / len(ingredients))
            for ing in ingredients:
                ing["weight_g"] = per

        kbju = calc_kbju(session, ingredients)

        result = {
            "food": data.get("food", "unknown"),
            "confidence": float(data.get("confidence", 0.5)),
            "ingredients": ingredients,
            **kbju,
            "source": "cv_v2"
        }

        try:
            redis_client.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

        return result

    except Exception as e:
        logger.exception(e)
        return fallback

    finally:
        session.close()


# ================= FEEDBACK =================

def learn_from_feedback(food_name: str, ingredients: list):
    try:
        logger.info(f"feedback received: {food_name} -> {len(ingredients)} ingredients")
    except Exception:
        pass
    return {"status": "ok"}


# ================= ASYNC WRAPPER =================

async def analyze_image_async(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, path)