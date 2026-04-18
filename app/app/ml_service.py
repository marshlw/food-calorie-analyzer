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
Ты эксперт по анализу еды.

ВАЖНО:
- Указывай ТОЛЬКО те ингредиенты, которые ЯВНО видны
- НЕ додумывай
- НЕ добавляй "по рецепту"

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
    "картошка": "картофель",
    "белый рис": "рис",
}

STOPWORDS = [
    "жареный", "жареная", "вареный", "отварной",
    "гриль", "свежий"
]


def normalize_text(text: str) -> str:
    text = text.lower()
    for w in STOPWORDS:
        text = text.replace(w, "")
    return text.strip()


# ===================== EMBEDDINGS =====================

EMBEDDING_CACHE = {}


def get_embedding(text: str):
    try:
        res = client.embeddings(
            model=settings.MODEL_NAME,
            prompt=text
        )
        return res["embedding"]
    except:
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


# ===================== MATCHING =====================

def match_ingredient(name: str):
    name = normalize_text(name)

    for key, value in NORMALIZATION_MAP.items():
        if key in name:
            return value

    match = process.extractOne(
        name,
        KBJU_DB.keys(),
        scorer=fuzz.token_sort_ratio
    )

    if match and match[1] > 80:
        return match[0]

    name_emb = get_cached_embedding(name)

    best, score = None, 0
    for k in KBJU_DB.keys():
        sim = cosine_similarity(name_emb, get_cached_embedding(k))
        if sim > score:
            best, score = k, sim

    if score > 0.75:
        return best

    redis_client.sadd("unmatched_ingredients", name)
    return None


# ===================== IMAGE =====================

def preprocess(path: str) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1024, 1024))

    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.3)

    out = UPLOAD_DIR / f"processed_{Path(path).name}"
    img.save(out, quality=85)
    return str(out)


def estimate_portion_size(path: str):
    try:
        img = Image.open(path)
        w, h = img.size
        area = w * h

        if area < 300_000:
            return "small"
        elif area < 1_000_000:
            return "medium"
        else:
            return "large"
    except:
        return "medium"


def get_image_hash(path: str):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


# ===================== JSON =====================

def extract_json(text: str):
    if not text:
        return None

    for attempt in [text, text.strip()]:
        try:
            return json.loads(attempt)
        except:
            pass

    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except:
        pass

    logger.warning(f"JSON parse failed: {text[:200]}")
    return None


# ===================== REDIS =====================

def get_cache(key):
    try:
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except:
        pass


def set_cache(key, val):
    try:
        redis_client.setex(key, settings.CACHE_TTL, json.dumps(val))
    except:
        pass


def cache_step(key, func):
    cached = get_cache(key)
    if cached:
        return cached
    res = func()
    if res:
        set_cache(key, res)
    return res


# ===================== 🧠 LEARNING =====================

def learn_from_feedback(food: str, ingredients: list):
    try:
        key = f"learn:{food.lower()}"
        redis_client.set(key, json.dumps(ingredients))
    except:
        pass


def get_learned_ingredients(food: str):
    try:
        key = f"learn:{food.lower()}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except:
        pass
    return None


# ===================== MODEL =====================

def call_model(prompt: str, image: str | None):
    msg = {"role": "user", "content": prompt}
    if image:
        msg["images"] = [image]

    res = client.chat(
        model=settings.MODEL_NAME,
        messages=[msg],
        options={"temperature": 0.1}
    )

    return extract_json(res["message"]["content"])


# ===================== STEPS =====================

def step_detect(image, h):
    return cache_step(
        f"{settings.CACHE_PREFIX}:dish:{h}",
        lambda: call_model(PROMPT_DETECT, image)
    ) or {"food": "неизвестно", "confidence": 0}


def step_ingredients(image, dish, h):
    learned = get_learned_ingredients(dish)
    if learned:
        return learned

    def run():
        r = call_model(PROMPT_INGREDIENTS, image)
        return r.get("ingredients", []) if r else []

    return cache_step(f"{settings.CACHE_PREFIX}:ing:{h}", run)


# ===================== WEIGHTS =====================

def normalize_total_weight(dish: str, portion: str):
    base = 250
    dish = dish.lower()

    if "салат" in dish:
        base = 300
    elif "wrap" in dish or "шаурма" in dish:
        base = 250
    elif "паста" in dish:
        base = 300

    if portion == "small":
        return int(base * 0.7)
    if portion == "large":
        return int(base * 1.3)

    return base


def smart_distribute(total_weight: int, ingredients: list):
    n = len(ingredients)
    if n == 0:
        return ingredients

    base = total_weight / n

    for i in ingredients:
        i["weight_g"] = round(base)

    return ingredients


# ===================== KBJU =====================

def calc_kbju(ings):
    total = dict(calories=0, protein_g=0, fat_g=0, carbs_g=0, weight_g=0)

    for i in ings:
        name = match_ingredient(i["name"])
        if not name:
            continue

        w = i["weight_g"]
        db = KBJU_DB[name]
        s = w / 100

        total["weight_g"] += w
        total["calories"] += db["calories"] * s
        total["protein_g"] += db["protein"] * s
        total["fat_g"] += db["fat"] * s
        total["carbs_g"] += db["carbs"] * s

    for k in total:
        total[k] = round(total[k], 1)

    return total


# ===================== MAIN =====================

def analyze_image_sync(path: str):
    fallback = {
        "food": "не распознано",
        "weight_g": 200,
        "calories": 250,
        "protein_g": 10,
        "fat_g": 10,
        "carbs_g": 30,
        "confidence": 0,
        "ingredients": [],
        "source": "fallback"
    }

    try:
        h = get_image_hash(path)
        key = f"{settings.CACHE_PREFIX}:final:{h}"

        cached = get_cache(key)
        if cached:
            cached["source"] = "cache"
            return cached

        img = preprocess(path)

        dish = step_detect(img, h)
        if dish["confidence"] < 0.4:
            return fallback

        portion = estimate_portion_size(path)

        ings = step_ingredients(img, dish["food"], h)
        ings = ings[:4]

        total_weight = normalize_total_weight(dish["food"], portion)
        ings = smart_distribute(total_weight, ings)

        kbju = calc_kbju(ings)

        result = {
            "food": dish["food"],
            "confidence": dish["confidence"],
            "ingredients": ings,
            **kbju,
            "source": "pipeline_v6"
        }

        set_cache(key, result)
        return result

    except Exception as e:
        logger.exception(e)
        return fallback


async def analyze_image_async(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, path)