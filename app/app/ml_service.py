import asyncio
import json
import logging
import re
import time
import hashlib
from pathlib import Path
from typing import Optional

import redis
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from google import genai

from .config import settings
from . import models

logger = logging.getLogger(__name__)

# ================= GEMINI =================

client = genai.Client(api_key=settings.GEMINI_API_KEY)

logger.info("Gemini client initialized")

# ================= MODELS =================

MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
]

WORKING_MODEL = None


def get_working_model():
    global WORKING_MODEL

    if WORKING_MODEL:
        return WORKING_MODEL

    try:
        available = [m.name for m in client.models.list()]
        logger.info(f"Available models: {available}")
    except Exception as e:
        logger.error(f"Failed to list models: {e}")
        available = []

    for model in MODEL_CANDIDATES:
        if any(model in m for m in available):
            WORKING_MODEL = model
            logger.info(f"Selected model: {model}")
            return model

    # fallback если list_models не дал результат
    WORKING_MODEL = MODEL_CANDIDATES[0]
    logger.warning(f"Fallback model: {WORKING_MODEL}")
    return WORKING_MODEL


# ================= REDIS =================

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

# ================= DB =================

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

# ================= FILES =================

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ================= RATE LIMIT =================

_last_call = 0


def rate_limit():
    global _last_call
    now = time.time()
    diff = now - _last_call
    if diff < 1.2:
        time.sleep(1.2 - diff)
    _last_call = time.time()


# ================= PROMPT =================

PROMPT_VERSION = "v6"

PROMPT = """
Ты анализируешь фото еды.

Верни СТРОГО JSON:

{
  "food": "название блюда",
  "ingredients": [
    {"name": "ингредиент", "type": "protein|carb|fat|vegetable"}
  ],
  "weight_g": число,
  "confidence": 0.0
}

ПРАВИЛА:
- максимум 6 ингредиентов
- только реальные ингредиенты
- weight_g от 100 до 800
- если не уверен:
{"food":"unknown","ingredients":[],"weight_g":200,"confidence":0.0}
"""


# ================= JSON =================

def extract_json(text: str) -> Optional[dict]:
    if not text:
        return None

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except:
        return None


# ================= GEMINI CALL =================

def call_gemini(prompt: str, image_path: Optional[str]):
    models_to_try = [settings.GEMINI_MODEL] + MODEL_CANDIDATES

    for model_name in models_to_try:
        for attempt in range(settings.MODEL_RETRY_ATTEMPTS + 1):
            try:
                rate_limit()

                contents = [prompt]

                if image_path:
                    img = Image.open(image_path)
                    contents.append(img)

                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                )

                logger.info(f"✅ Gemini success with model: {model_name}")
                return response.text

            except Exception as e:
                logger.error(f"❌ {model_name} attempt {attempt}: {e}")

                if attempt >= settings.MODEL_RETRY_ATTEMPTS:
                    break

                time.sleep(settings.MODEL_BACKOFF_FACTOR * (attempt + 1))

    logger.error("🚨 All Gemini models failed")
    return None


# ================= IMAGE =================

def preprocess(path: str) -> str:
    try:
        img = Image.open(path).convert("RGB")
        img.thumbnail((settings.MAX_IMAGE_SIZE, settings.MAX_IMAGE_SIZE))

        out = UPLOAD_DIR / f"p_{Path(path).name}"
        img.save(out, "JPEG", quality=settings.IMAGE_QUALITY)

        return str(out)
    except Exception as e:
        logger.warning(f"Image error: {e}")
        return path


def get_hash(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


# ================= DB =================

def get_product(session, name: str):
    return session.query(models.Product).filter(
        models.Product.name == name.lower()
    ).first()


# ================= KBJU =================

def calc_kbju(session, ingredients):
    total = {"calories": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0}

    for ing in ingredients:
        product = get_product(session, ing["name"])
        w = ing.get("weight_g", 50)

        if product:
            k = w / 100
            total["calories"] += product.calories * k
            total["protein_g"] += product.protein * k
            total["fat_g"] += product.fat * k
            total["carbs_g"] += product.carbs * k

    return total


# ================= MAIN =================

def analyze_image_sync(path: str) -> dict:
    fallback = {
        "food": "unknown",
        "weight_g": 200,
        "calories": 200,
        "protein_g": 10,
        "fat_g": 10,
        "carbs_g": 20,
        "confidence": 0.0,
        "ingredients": [],
    }

    session = SessionLocal()

    try:
        cache_key = f"{settings.CACHE_PREFIX}:{PROMPT_VERSION}:{get_hash(path)}"

        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)

        img = preprocess(path)

        raw = call_gemini(PROMPT, img)
        data = extract_json(raw)

        if not data:
            return fallback

        ingredients = data.get("ingredients", [])
        total_weight = data.get("weight_g", 200)

        per_item = max(20, total_weight // max(len(ingredients), 1))

        for ing in ingredients:
            ing["weight_g"] = per_item

        kbju = calc_kbju(session, ingredients)

        result = {
            "food": data.get("food"),
            "confidence": data.get("confidence", 0.5),
            "weight_g": total_weight,
            "ingredients": ingredients,
            **kbju,
        }

        redis_client.setex(
            cache_key,
            settings.CACHE_TTL,
            json.dumps(result, ensure_ascii=False)
        )

        return result

    except Exception as e:
        logger.error(e)
        return fallback

    finally:
        session.close()


# ================= ASYNC =================

async def analyze_image_async(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, path)


def analyze_image(path: str) -> dict:
    return analyze_image_sync(path)