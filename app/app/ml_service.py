import asyncio
import json
import logging
import re
import time
import hashlib
import base64
from pathlib import Path
from typing import Optional

import redis
import requests
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from google import genai

from .config import *
from . import models

logger = logging.getLogger(__name__)

# ================= GEMINI =================

client = genai.Client(api_key=settings.GEMINI_API_KEY)

logger.info("Gemini client initialized")

MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
]

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

_last_gemini_call = 0
_last_deepseek_call = 0


def rate_limit(last_call_holder: dict, key: str):
    now = time.time()
    diff = now - last_call_holder.get(key, 0)
    if diff < 1.2:
        time.sleep(1.2 - diff)
    last_call_holder[key] = time.time()


# ================= PROMPT =================

PROMPT_VERSION = "v7"

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


# ================= GEMINI =================

def is_quota_error(e: Exception) -> bool:
    return "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)


def call_gemini(prompt: str, image_path: Optional[str]):
    for model_name in [settings.GEMINI_MODEL] + MODEL_CANDIDATES:
        try:
            rate_limit(globals(), "_last_gemini_call")

            contents = [prompt]

            if image_path:
                img = Image.open(image_path)
                contents.append(img)

            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )

            logger.info(f"✅ Gemini success: {model_name}")
            return response.text

        except Exception as e:
            if is_quota_error(e):
                logger.warning(f"🚫 Gemini quota exceeded: {model_name}")
                return None  # 💥 СРАЗУ fallback

            logger.error(f"❌ Gemini error ({model_name}): {e}")
            time.sleep(1)

    return None


# ================= DEEPSEEK =================

def call_deepseek_vision(prompt: str, image_path: str) -> Optional[str]:
    if not settings.DEEPSEEK_API_KEY:
        logger.warning("No DeepSeek API key")
        return None

    # 1. Кодируем картинку в base64
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")

    # 2. Формируем тело запроса для vision-модели
    payload = {
        "model": settings.DEEPSEEK_VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_data}",
                            # "detail": "high" # Можно добавить для детализации
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0,
        # "max_tokens": 500 # Можно ограничить
    }

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    # 3. Отправляем запрос на правильный URL
    response = requests.post(
        settings.DEEPSEEK_VISION_API_URL,
        json=payload,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


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

        # 🔥 Gemini → сразу fallback если quota
        raw = call_gemini(PROMPT, img)
        data = extract_json(raw)

        if not data:
            logger.info("Fallback to DeepSeek...")
            raw = call_deepseek_vision(PROMPT, img)
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
        logger.error(f"Unexpected error: {e}")
        return fallback

    finally:
        session.close()


async def analyze_image_async(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, path)


def analyze_image(path: str) -> dict:
    return analyze_image_sync(path)