import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Dict, Any

import ollama
from PIL import Image, ImageEnhance

from .config import settings

client = ollama.Client(host="http://ollama:11434")

logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("/app/app/uploads")

KBJU_DB = {
    "курица": {"calories": 165, "protein": 31, "fat": 3.6, "carbs": 0},
    "рис": {"calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28},
    "гречка": {"calories": 110, "protein": 4, "fat": 1.3, "carbs": 23},
    "картофель": {"calories": 100, "protein": 2, "fat": 0.1, "carbs": 17},
}

PROMPT = """
Ты эксперт по питанию.

Верни строго JSON:

{
 "food": "название блюда",
 "weight_g": число,
 "calories": число,
 "protein_g": число,
 "fat_g": число,
 "carbs_g": число,
 "confidence": 0.0-1.0
}
"""


def preprocess(path: str) -> str:
    img = Image.open(path).convert("RGB")
    img.thumbnail((1024, 1024))

    img = ImageEnhance.Contrast(img).enhance(1.2)
    img = ImageEnhance.Sharpness(img).enhance(1.3)

    # ✅ сохраняем рядом
    temp_path = UPLOAD_DIR / f"processed_{Path(path).name}"
    img.save(temp_path, quality=85)

    return str(temp_path)


def extract_json(text: str):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return json.loads(match.group()) if match else None


def validate_kbju(result: Dict[str, Any]) -> Dict[str, Any]:
    weight = result.get("weight_g", 200)

    max_cal = weight * 9
    min_cal = weight * 0.5

    result["calories"] = max(min(result["calories"], max_cal), min_cal)
    result["protein_g"] = min(result["protein_g"], weight)
    result["fat_g"] = min(result["fat_g"], weight)
    result["carbs_g"] = min(result["carbs_g"], weight)

    return result


def db_correction(result: Dict[str, Any]) -> Dict[str, Any]:
    food = result.get("food", "").lower()

    for key, db in KBJU_DB.items():
        if key in food:
            weight = result["weight_g"]
            scale = weight / 100

            result["calories"] = round(db["calories"] * scale)
            result["protein_g"] = round(db["protein"] * scale, 1)
            result["fat_g"] = round(db["fat"] * scale, 1)
            result["carbs_g"] = round(db["carbs"] * scale, 1)

            result["source"] = "db_override"
            return result

    result["source"] = "model"
    return result


async def analyze_image_async(image_path: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, image_path)


def analyze_image_sync(image_path: str) -> Dict[str, Any]:
    fallback = {
        "food": "Не распознано",
        "weight_g": 200,
        "calories": 250,
        "protein_g": 15,
        "fat_g": 10,
        "carbs_g": 25,
        "confidence": 0.0,
        "source": "fallback"
    }

    try:
        processed = preprocess(image_path)

        response = client.chat(
            model=settings.MODEL_NAME,
            messages=[{
                "role": "user",
                "content": PROMPT,
                "images": [processed]
            }],
            options={"temperature": 0.2}
        )

        parsed = extract_json(response["message"]["content"])
        if not parsed:
            return fallback

        if parsed.get("confidence", 0) < 0.4:
            return fallback

        parsed = validate_kbju(parsed)
        parsed = db_correction(parsed)

        return parsed

    except Exception as e:
        logger.exception(e)
        return fallback