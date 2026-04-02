import asyncio
import json
import logging
from pathlib import Path
from typing import Dict, Any

import ollama
from PIL import Image, ImageEnhance

from .config import settings

logger = logging.getLogger(__name__)

# ---------- База данных КБЖУ для часто встречающихся блюд (на 100 г) ----------
KBJU_DB = {
    "куриный шницель": {"calories": 200, "protein": 25, "fat": 8, "carbs": 10, "weight": 100},
    "булгур": {"calories": 120, "protein": 4, "fat": 1, "carbs": 25, "weight": 100},
    "куриное филе": {"calories": 165, "protein": 31, "fat": 3.6, "carbs": 0, "weight": 100},
    "греческий салат": {"calories": 90, "protein": 4, "fat": 7, "carbs": 4, "weight": 100},
    "овощной салат с тунцом": {"calories": 80, "protein": 6, "fat": 4, "carbs": 5, "weight": 100},
    "рис отварной": {"calories": 130, "protein": 2.7, "fat": 0.3, "carbs": 28, "weight": 100},
    "картофельное пюре": {"calories": 106, "protein": 2, "fat": 4, "carbs": 16, "weight": 100},
    # Добавьте при необходимости другие блюда
}

# ---------- Клиент Ollama ----------
client = ollama.Client(host=settings.OLLAMA_HOST)

# ---------- Улучшенный PROMPT ----------
PROMPT = """Ты — эксперт по распознаванию еды и расчету КБЖУ.
Анализируй изображение и возвращай **ТОЛЬКО валидный JSON** с такими полями:
- `food`: название блюда на русском (например, "куриный шницель с булгуром", "греческий салат").
- `weight_g`: вес порции в граммах (реалистично, 100–500 г).
- `calories`: калорийность порции (ккал).
- `protein_g`, `fat_g`, `carbs_g`: белки, жиры, углеводы в граммах.
- `confidence`: уверенность (0.1–1.0).
- `ingredients` (опционально): список ингредиентов на русском.

**Правила:**
1. Если блюдо составное (например, шницель + гарнир), указывай оба компонента в `food`.
2. Если не уверен — снижай `confidence`, но не ставь "неизвестно" сразу.
3. Для простых блюд (курица, рис) используй стандартные значения КБЖУ из базы данных.
4. Если изображение некачественное, возвращай `confidence: 0.1` и вес 0.

**Примеры:**
```json
{
  "food": "куриный шницель с булгуром",
  "weight_g": 350,
  "calories": 450,
  "protein_g": 35,
  "fat_g": 15,
  "carbs_g": 40,
  "confidence": 0.85,
  "ingredients": ["куриное филе", "панировка", "булгур", "масло растительное"]
}
{
  "food": "овощной салат с тунцом",
  "weight_g": 250,
  "calories": 200,
  "protein_g": 15,
  "fat_g": 10,
  "carbs_g": 12,
  "confidence": 0.9
  "ingredients": ["консервированный тунец", "помидоры", "руккола", "кукуруза консервированная", "оливковое масло"]
}
Возвращай ТОЛЬКО JSON без пояснений!"""

# ---------- Предобработка изображения ----------
def preprocess_image(image_path: str) -> str:
    """
    Улучшает качество изображения: повышает контрастность и резкость.
    Возвращает путь к временному обработанному файлу.
    """
    img = Image.open(image_path)

    # Проверка разрешения
    if img.size[0] < 500 or img.size[1] < 500:
        logger.warning(f"Low resolution image: {img.size}, results may be inaccurate")

    # Увеличение контрастности и резкости
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.5)
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(2.0)

    # Сохранение во временный файл
    temp_path = f"temp_{Path(image_path).name}"
    img.save(temp_path)
    return temp_path

# ---------- Постобработка ответа модели ----------
def postprocess_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Исправляет очевидные ошибки и заполняет пропуски."""
    # Если модель вернула "неизвестно", но вес > 0 — исправляем
    if result.get("food") == "неизвестно" and result.get("weight_g", 0) > 0:
        result["food"] = "блюдо не распознано"
        result["confidence"] = 0.3

    # Если калорийность 0, но вес > 0 — подставляем средние значения
    if result.get("calories", 0) == 0 and result.get("weight_g", 0) > 0:
        w = result["weight_g"]
        result["calories"] = int(w * 1.5)           # ~1.5 ккал/г
        result["protein_g"] = round(w * 0.05, 1)    # 5% белка
        result["fat_g"] = round(w * 0.03, 1)        # 3% жира
        result["carbs_g"] = round(w * 0.15, 1)      # 15% углеводов
        result["confidence"] = 0.4

    return result

# ---------- Применение базы данных КБЖУ ----------
def apply_kbju_db(result: Dict[str, Any]) -> Dict[str, Any]:
    """Если распознанное блюдо есть в базе, пересчитывает КБЖУ пропорционально весу."""
    food_name = result.get("food", "").lower()
    weight = result.get("weight_g", 0)
    if weight <= 0:
        return result

    for dish, values in KBJU_DB.items():
        if dish in food_name:
            scale = weight / values["weight"]
            result["calories"] = int(values["calories"] * scale)
            result["protein_g"] = round(values["protein"] * scale, 1)
            result["fat_g"] = round(values["fat"] * scale, 1)
            result["carbs_g"] = round(values["carbs"] * scale, 1)
            result["confidence"] = min(0.95, result.get("confidence", 0.5) + 0.1)
            logger.info(f"Applied KBJU DB for '{dish}': scale={scale:.2f}")
            break
    return result

# ---------- Синхронный анализ изображения ----------
def analyze_image_sync(image_path: str) -> Dict[str, Any]:
    raw_content = ""
    temp_path = None
    try:
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        # Предобработка изображения
        temp_path = preprocess_image(image_path)
        logger.info(f"Preprocessed image: {temp_path} (original: {image_path})")

        # Запрос к модели
        response = client.chat(
            model=settings.MODEL_NAME,
            messages=[
                {
                    'role': 'user',
                    'content': PROMPT,
                    'images': [temp_path]
                }
            ],
            format='json',
            options={
                'temperature': 0.3,
                'num_ctx': 8192,
                'num_predict': 1000,
                'top_k': 50,
                'top_p': 0.9,
            }
        )

        raw_content = response['message']['content'].strip()
        logger.info(f"Raw model response: {raw_content}")

        # Очистка от markdown-разметки
        if raw_content.startswith('```'):
            raw_content = raw_content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        result = json.loads(raw_content)

        # Валидация обязательных полей
        required = ['food', 'weight_g', 'calories', 'protein_g', 'fat_g', 'carbs_g', 'confidence']
        for field in required:
            if field not in result:
                logger.warning(f"Missing field {field}, using default")
                defaults = {
                    'food': "unknown",
                    'weight_g': 250,
                    'calories': 300,
                    'protein_g': 10,
                    'fat_g': 10,
                    'carbs_g': 30,
                    'confidence': 0.5
                }
                result[field] = defaults[field]

        # Нормализация числовых полей
        result['weight_g'] = max(1, min(5000, int(result['weight_g'])))
        result['calories'] = max(0, min(10000, int(result['calories'])))
        result['protein_g'] = max(0, round(float(result['protein_g']), 1))
        result['fat_g'] = max(0, round(float(result['fat_g']), 1))
        result['carbs_g'] = max(0, round(float(result['carbs_g']), 1))
        result['confidence'] = max(0.0, min(1.0, float(result['confidence'])))

        # Постобработка и применение базы данных
        result = postprocess_result(result)
        result = apply_kbju_db(result)

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}, raw: {raw_content}")
        return {"error": "invalid_json", "detail": str(e), "raw": raw_content}
    except Exception as e:
        logger.exception(f"ML service error: {e}")
        return {"error": "ml_error", "detail": str(e)}
    finally:
        # Удаляем временный файл, если он был создан
        if temp_path and Path(temp_path).exists():
            Path(temp_path).unlink()
            logger.debug(f"Removed temporary file: {temp_path}")

# ---------- Асинхронная обёртка ----------
async def analyze_image_async(image_path: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, image_path)