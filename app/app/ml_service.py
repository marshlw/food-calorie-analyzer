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

# Глобальная переменная для текущей модели
current_model = settings.MODEL_NAME


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

def update_model(new_model: str):
    global current_model
    current_model = new_model
    logger.info(f"Model updated to: {current_model}")

def call_model(prompt: str, image: str | None = None) -> Optional[dict]:
    try:
        msg = {"role": "user", "content": prompt}
        if image:
            msg["images"] = [image]

        res = client.chat(
            model=current_model,
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
Ты AI-ассистент для анализа еды на фото. Твоя задача:
1. Точно определить название блюда
2. Перечислить основные ингредиенты (максимум 5-6)
3. Дать уверенность в предсказании

Верни СТРОГО JSON, БЕЗ MARKDOWN:

{
  "food": "точное название блюда на русском",
  "ingredients": [
    {"name": "основной ингредиент", "type": "protein|carb|fat|vegetable"},
    {"name": "второстепенный ингредиент", "type": "..."}
  ],
  "confidence": 0.0
}

ПРАВИЛА:
- Перечисли ТОЛЬКО видимые ингредиенты (максимум 6)
- Не добавляй лишнего или неправдоподобного
- Типизируй ингредиенты для лучшей калорийности
- confidence: 0.95 если уверен, 0.5 если сомневаешься, 0.2 если неясно
- Если это блюдо ты видишь впервые, ставь confidence 0.3-0.5
- Возвращай ТОЛЬКО JSON, БЕЗ текста и markdown кода
"""

PROMPT_WEIGHT = """
Оцени примерный вес еды на фото в граммах.
Учитывай:
- Размер порции на тарелке
- Типичные размеры посуды
- Плотность пищи (каша тяжелее, чем салат)

Верни ТОЛЬКО JSON без markdown:
{"weight_g": число_от_50_до_1000}

Если уверен не можешь — верни 200-300.
"""

PROMPT_WEIGHT_CONFIDENCE = """
Оцени насколько точно можно определить вес этого блюда.
Возвращай число от 0 до 1.

Верни ТОЛЬКО JSON:
{"weight_confidence": 0.0}
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

# Типичные соотношения калорийности (вспомогательные)
INGREDIENT_TYPES = {
    "protein": {"calories_per_100g": 165, "protein": 25, "fat": 8, "carbs": 0},
    "carb": {"calories_per_100g": 150, "protein": 3, "fat": 0.5, "carbs": 35},
    "fat": {"calories_per_100g": 720, "protein": 0, "fat": 80, "carbs": 0},
    "vegetable": {"calories_per_100g": 30, "protein": 2, "fat": 0.3, "carbs": 5},
}

def validate_and_fix_kbju(kbju: dict, weight_g: int) -> dict:
    """
    Валидирует KBJU и проверяет разумность значений.
    Если что-то странное, пытается исправить.
    """
    # Минимальные значения
    if kbju["calories"] < 10:
        kbju["calories"] = max(50, weight_g * 0.5)  # примерно 0.5 ккал/г
    if kbju["protein_g"] < 0.5:
        kbju["protein_g"] = weight_g * 0.05  # 5% белков
    if kbju["fat_g"] < 0.3:
        kbju["fat_g"] = weight_g * 0.02  # 2% жиров
    if kbju["carbs_g"] < 0.5:
        kbju["carbs_g"] = weight_g * 0.10  # 10% углеводов

    # Проверка соответствия калорий (примерно)
    # 1г белка/углеводов = 4 ккал, 1г жира = 9 ккал
    calculated_calories = (kbju["protein_g"] + kbju["carbs_g"]) * 4 + kbju["fat_g"] * 9
    actual_calories = kbju["calories"]

    # Если разница > 50%, попытаемся скорректировать
    if actual_calories > 0 and calculated_calories > 0:
        ratio = calculated_calories / actual_calories
        if ratio > 1.5 or ratio < 0.5:
            # Скорректируем углеводы как самый гибкий компонент
            remaining = actual_calories - (kbju["protein_g"] * 4 + kbju["fat_g"] * 9)
            if remaining > 0:
                kbju["carbs_g"] = remaining / 4
            else:
                kbju["carbs_g"] = max(0.5, actual_calories * 0.5 / 4)

    # Округляем и возвращаем
    return {k: max(0, round(v, 1)) for k, v in kbju.items()}


def distribute_weight_by_type(total_weight: int, ingredients: List[dict]) -> None:
    """
    Распределяет вес ингредиентов на основе их типа.
    Жидкие компоненты занимают больше места, белки - меньше.
    """
    if not ingredients:
        return

    # Оцениваем типы и даём веса (в процентах от всей массы)
    type_weights = {
        "protein": 0.25,  # мясо занимает ~25%
        "carb": 0.40,     # углеводы (рис, паста) ~40%
        "fat": 0.10,      # масла/сливки ~10%
        "vegetable": 0.25 # овощи ~25%
    }

    total_percent = 0
    for ing in ingredients:
        ing_type = ing.get("type", "carb")
        total_percent += type_weights.get(ing_type, 0.2)

    # Нормализуем и раздаём вес
    for ing in ingredients:
        ing_type = ing.get("type", "carb")
        weight_ratio = type_weights.get(ing_type, 0.2) / max(total_percent, 1)
        ing["weight_g"] = max(20, int(total_weight * weight_ratio))


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
        ing_type = ing.get("type", "carb")
        w = ing.get("weight_g", 0)

        # Пытаемся найти в БД
        product = get_product(session, name)

        if product:
            k = w / 100
            total["calories"] += product.calories * k
            total["protein_g"] += product.protein * k
            total["fat_g"] += product.fat * k
            total["carbs_g"] += product.carbs * k
        else:
            # Fallback: используем типичные значения для типа
            defaults = INGREDIENT_TYPES.get(ing_type, INGREDIENT_TYPES["carb"])
            k = w / 100
            total["calories"] += defaults["calories_per_100g"] * k
            total["protein_g"] += defaults["protein"] * k
            total["fat_g"] += defaults["fat"] * k
            total["carbs_g"] += defaults["carbs"] * k

        total["weight_g"] += w

    if total["weight_g"] == 0:
        total["weight_g"] = 200

    return validate_and_fix_kbju(total, int(total["weight_g"]))


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
                cached_data = json.loads(cached)
                cached_data["source"] = "cache"
                return cached_data
        except Exception:
            pass

        img = preprocess(path)

        data = call_model(PROMPT, img)
        if not data:
            return fallback

        food_name = data.get("food", "unknown")
        ingredients = (data.get("ingredients") or [])[:6]  # максимум 6 ингредиентов
        if not ingredients:
            return fallback

        # Оцениваем вес
        cv_w = estimate_weight_cv(img)
        llm_w = estimate_weight_llm(img)
        weight_confidence = 0.6  # средняя уверенность в весе

        # Взвешиваем весы
        total_weight = max(150, combine_weights(cv_w, llm_w))

        # Распределяем вес по ингредиентам
        distribute_weight_by_type(total_weight, ingredients)

        # Считаем KBJU
        kbju = calc_kbju(session, ingredients)

        # Оцениваем общую уверенность
        confidence = float(data.get("confidence", 0.5))
        
        # Понижаем уверенность если ингредиентов < 3 или нет в БД
        found_in_db = sum(1 for ing in ingredients if get_product(session, ing.get("name", "").lower()))
        if found_in_db < len(ingredients) * 0.5:
            confidence *= 0.8  # понижаем на 20%

        result = {
            "food": food_name,
            "confidence": round(confidence, 2),
            "ingredients": ingredients,
            **kbju,
            "source": "ml_v2"
        }

        try:
            redis_client.setex(cache_key, 3600, json.dumps(result))
        except Exception:
            pass

        return result

    except Exception as e:
        logger.exception(f"Error in analyze_image_sync: {e}")
        return fallback

    finally:
        try:
            session.close()
        except Exception:
            pass


# ================= FEEDBACK =================

def learn_from_feedback(food_name: str, ingredients: list):
    """
    Учимся на основе исправлений пользователей.
    Сохраняем правильное распределение ингредиентов для похожих блюд.
    """
    try:
        session = SessionLocal()
        
        if not food_name or not ingredients:
            return {"status": "empty"}

        # Нормализуем название
        food_name = food_name.lower().strip()
        
        # Обновляем или создаём продукты из feedback
        for ing in ingredients:
            ing_name = ing.get("name", "").lower().strip()
            if not ing_name or len(ing_name) < 2:
                continue

            # Проверяем, есть ли продукт
            product = get_product(session, ing_name)
            
            if not product:
                # Оцениваем нутриенты по типу
                ing_type = ing.get("type", "carb")
                defaults = INGREDIENT_TYPES.get(ing_type, INGREDIENT_TYPES["carb"])
                
                new_product = models.Product(
                    name=ing_name,
                    calories=defaults["calories_per_100g"],
                    protein=defaults["protein"],
                    fat=defaults["fat"],
                    carbs=defaults["carbs"]
                )
                session.add(new_product)
                logger.info(f"Added new product from feedback: {ing_name}")

        session.commit()
        logger.info(f"Learning from feedback: {food_name} with {len(ingredients)} ingredients")
        return {"status": "ok", "learned": len(ingredients)}

    except Exception as e:
        logger.warning(f"Learning error: {e}")
        return {"status": "error", "error": str(e)}
    finally:
        try:
            session.close()
        except Exception:
            pass


# ================= ASYNC WRAPPER =================

async def analyze_image_async(path: str):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, path)