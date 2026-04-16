import asyncio
import json
import logging
import re
import hashlib
from pathlib import Path
from typing import Dict, Any, List

import ollama
import redis
import numpy as np
from rapidfuzz import process, fuzz
from PIL import Image, ImageEnhance

from .config import settings

# ===================== INIT =====================

client = ollama.Client(host=settings.OLLAMA_HOST)

redis_client = redis.Redis(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    decode_responses=True
)

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path(settings.UPLOAD_DIR)

# ===================== KBJU DB =====================

KBJU_DB = {
    "курица": {"calories": 165, "protein": 31, "fat": 3.6, "carbs": 0},
    "рис": {"calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28},
    "гречка": {"calories": 110, "protein": 4, "fat": 1.3, "carbs": 23},
    "картофель": {"calories": 100, "protein": 2, "fat": 0.1, "carbs": 17},
}

# ===================== PROMPTS =====================

PROMPT_DETECT = """
Определи блюдо на изображении.

Верни строго JSON:
{
 "food": "название блюда",
 "confidence": 0.0-1.0
}
"""

PROMPT_INGREDIENTS = """
Ты эксперт по питанию.

Разбери блюдо на ингредиенты с примерным весом.

Верни строго JSON:
{
 "ingredients": [
   {"name": "ингредиент", "weight_g": число}
 ]
}
"""

# ===================== NORMALIZATION =====================

NORMALIZATION_MAP = {
    "куриная грудка": "курица",
    "куриное филе": "курица",
    "жареная курица": "курица",
    "белый рис": "рис",
    "бурый рис": "рис",
    "рис отварной": "рис",
    "картошка": "картофель",
    "картофель фри": "картофель",
}

STOPWORDS = [
    "жареный", "жареная", "вареный", "вареная",
    "отварной", "отварная", "на пару", "гриль",
    "свежий", "свежая"
]


def normalize_text(text: str) -> str:
    text = text.lower()
    for w in STOPWORDS:
        text = text.replace(w, "")
    return text.strip()


# ===================== EMBEDDINGS =====================

EMBEDDING_CACHE = {}


def get_embedding(text: str) -> list:
    try:
        response = client.embeddings(
            model=settings.MODEL_NAME,
            prompt=text
        )
        return response["embedding"]
    except Exception as e:
        logger.warning(f"Embedding error: {e}")
        return []


def cosine_similarity(a, b):
    if not a or not b:
        return 0
    a, b = np.array(a), np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))


def get_cached_embedding(text: str):
    if text in EMBEDDING_CACHE:
        return EMBEDDING_CACHE[text]
    emb = get_embedding(text)
    EMBEDDING_CACHE[text] = emb
    return emb


# ===================== AUTO LEARNING =====================

def save_unmatched(name: str):
    try:
        redis_client.sadd("unmatched_ingredients", name)
    except Exception:
        pass


# ===================== MATCHING =====================

def match_ingredient(name: str, threshold: int = 80) -> str | None:
    name = normalize_text(name)

    # 1. словарь
    for key, value in NORMALIZATION_MAP.items():
        if key in name:
            return value

    # 2. fuzzy
    choices = list(KBJU_DB.keys())

    match = process.extractOne(
        name,
        choices,
        scorer=fuzz.token_sort_ratio
    )

    if match and match[1] >= threshold:
        return match[0]

    # 3. embeddings fallback
    name_emb = get_cached_embedding(name)

    best_match = None
    best_score = 0

    for key in choices:
        key_emb = get_cached_embedding(key)
        sim = cosine_similarity(name_emb, key_emb)

        if sim > best_score:
            best_score = sim
            best_match = key

    if best_score > 0.75:
        return best_match

    save_unmatched(name)
    return None


# ===================== IMAGE =====================

def preprocess(path: str) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((settings.MAX_IMAGE_SIZE, settings.MAX_IMAGE_SIZE))

    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Brightness(img).enhance(1.05)

    temp_path = UPLOAD_DIR / f"processed_{Path(path).name}"
    img.save(temp_path, quality=settings.IMAGE_QUALITY)

    return str(temp_path)


def get_image_hash(path: str) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def extract_json(text: str):
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    return None


# ===================== REDIS =====================

def get_cache(key: str):
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.warning(f"Redis GET error: {e}")
    return None


def set_cache(key: str, value: dict):
    try:
        redis_client.setex(key, settings.CACHE_TTL, json.dumps(value))
    except Exception as e:
        logger.warning(f"Redis SET error: {e}")


def cache_step(key: str, func):
    cached = get_cache(key)
    if cached:
        return cached

    result = func()
    if result:
        set_cache(key, result)

    return result


# ===================== MODEL =====================

def call_model(prompt: str, image: str):
    response = client.chat(
        model=settings.MODEL_NAME,
        messages=[{
            "role": "user",
            "content": prompt,
            "images": [image]
        }],
        options={"temperature": 0.1}
    )

    return extract_json(response["message"]["content"])


# ===================== STEPS =====================

def step_detect_dish(image: str, image_hash: str):
    key = f"{settings.CACHE_PREFIX}:dish:{image_hash}"

    def run():
        return call_model(PROMPT_DETECT, image)

    return cache_step(key, run) or {"food": "Не распознано", "confidence": 0.0}


def step_ingredients(image: str, image_hash: str):
    key = f"{settings.CACHE_PREFIX}:ingredients:{image_hash}"

    def run():
        result = call_model(PROMPT_INGREDIENTS, image)
        return result.get("ingredients", []) if result else []

    return cache_step(key, run) or []


# ===================== KBJU =====================

def calc_kbju(ingredients: List[Dict[str, Any]]) -> Dict[str, float]:
    total = {
        "calories": 0,
        "protein_g": 0,
        "fat_g": 0,
        "carbs_g": 0,
        "weight_g": 0
    }

    for item in ingredients:
        raw_name = item.get("name", "")
        weight = item.get("weight_g", 0)

        total["weight_g"] += weight

        matched = match_ingredient(raw_name)

        if not matched:
            logger.warning(f"UNMATCHED: {raw_name}")
            continue

        db = KBJU_DB[matched]
        scale = weight / 100

        total["calories"] += db["calories"] * scale
        total["protein_g"] += db["protein"] * scale
        total["fat_g"] += db["fat"] * scale
        total["carbs_g"] += db["carbs"] * scale

    total["calories"] = round(total["calories"])
    total["protein_g"] = round(total["protein_g"], 1)
    total["fat_g"] = round(total["fat_g"], 1)
    total["carbs_g"] = round(total["carbs_g"], 1)
    total["weight_g"] = round(total["weight_g"])

    return total


# ===================== VALIDATION =====================

def validate_result(result: Dict[str, Any]) -> Dict[str, Any]:
    weight = result.get("weight_g", 200)

    result["calories"] = max(min(result["calories"], weight * 9), weight * 0.5)
    result["protein_g"] = min(result["protein_g"], weight)
    result["fat_g"] = min(result["fat_g"], weight)
    result["carbs_g"] = min(result["carbs_g"], weight)

    return result


# ===================== MAIN =====================

def analyze_image_sync(image_path: str) -> Dict[str, Any]:
    fallback = {
        "food": "Не распознано",
        "weight_g": 200,
        "calories": 250,
        "protein_g": 15,
        "fat_g": 10,
        "carbs_g": 25,
        "confidence": 0.0,
        "ingredients": [],
        "source": "fallback"
    }

    try:
        image_hash = get_image_hash(image_path)
        cache_key = f"{settings.CACHE_PREFIX}:final:{image_hash}"

        cached = get_cache(cache_key)
        if cached:
            cached["source"] = "cache"
            return cached

        processed = preprocess(image_path)

        dish = step_detect_dish(processed, image_hash)
        if dish["confidence"] < 0.4:
            return fallback

        ingredients = step_ingredients(processed, image_hash)
        if not ingredients:
            return fallback

        kbju = calc_kbju(ingredients)

        result = {
            "food": dish["food"],
            "confidence": dish["confidence"],
            "ingredients": ingredients,
            **kbju,
            "source": "pipeline_v3"
        }

        result = validate_result(result)

        set_cache(cache_key, result)

        return result

    except Exception as e:
        logger.exception(e)
        return fallback


async def analyze_image_async(image_path: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, image_path)