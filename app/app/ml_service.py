import asyncio
import json
import logging
from typing import Dict, Any
from pathlib import Path
import ollama
from .config import settings

logger = logging.getLogger(__name__)

client = ollama.Client(host=settings.OLLAMA_HOST)

PROMPT = """
Ты — эксперт-нутрициолог. Проанализируй изображение еды и верни ТОЛЬКО JSON.

Правила:
1. Определи название блюда/продукта на русском языке (например: "борщ", "овощной салат", "куриный суп", "яблоко").
2. Оцени примерный вес порции в граммах (стандартная тарелка: 300-400г, чашка: 200-300мл).
3. Рассчитай калории, белки, жиры, углеводы на эту порцию.
4. Укажи уверенность (0.0-1.0): 0.9+ если точно знаешь, 0.5-0.8 если есть сомнения, 0.1-0.4 если очень не уверен.
5. ВСЕГДА возвращай ВСЕ поля: food, weight_g, calories, protein_g, fat_g, carbs_g, confidence.
   Если не уверен в каком-то параметре, дай приблизительную оценку, но confidence сделай низким.
6. Если на фото совсем нет еды или качество ужасное, верни food = "unknown", все показатели 0, confidence = 0.1.

Примеры:
{"food": "борщ", "weight_g": 350, "calories": 120, "protein_g": 8, "fat_g": 5, "carbs_g": 15, "confidence": 0.85}
{"food": "салат овощной", "weight_g": 250, "calories": 80, "protein_g": 2, "fat_g": 5, "carbs_g": 10, "confidence": 0.9}
{"food": "куриный суп", "weight_g": 300, "calories": 150, "protein_g": 12, "fat_g": 6, "carbs_g": 10, "confidence": 0.7}
{"food": "unknown", "weight_g": 0, "calories": 0, "protein_g": 0, "fat_g": 0, "carbs_g": 0, "confidence": 0.1}

Верни ТОЛЬКО валидный JSON без markdown и пояснений!
"""

async def analyze_image_async(image_path: str) -> Dict[str, Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_image_sync, image_path)

def analyze_image_sync(image_path: str) -> Dict[str, Any]:
    raw_content = ""
    try:
        if not Path(image_path).exists():
            raise FileNotFoundError(f"Image not found: {image_path}")

        response = client.chat(
            model=settings.MODEL_NAME,
            messages=[
                {
                    'role': 'user',
                    'content': PROMPT,
                    'images': [image_path]
                }
            ],
            format='json',
            options={
                'temperature': 0.4,
                'num_ctx': 4096,
                'num_predict': 300,
            }
        )

        raw_content = response['message']['content'].strip()
        logger.info(f"Raw model response: {raw_content}")  # <-- добавили для отладки

        # Очистка от markdown
        if raw_content.startswith('```'):
            raw_content = raw_content.split('\n', 1)[1].rsplit('```', 1)[0].strip()

        result = json.loads(raw_content)

        # Если модель вернула ошибку
        if "error" in result:
            return result

        # Валидация полей
        required = ['food', 'weight_g', 'calories', 'protein_g', 'fat_g', 'carbs_g', 'confidence']
        for field in required:
            if field not in result:
                logger.warning(f"Missing field {field}, using default")
                if field == 'food':
                    result['food'] = "unknown"
                elif field == 'weight_g':
                    result['weight_g'] = 250
                elif field == 'calories':
                    result['calories'] = 300
                elif field == 'protein_g':
                    result['protein_g'] = 10
                elif field == 'fat_g':
                    result['fat_g'] = 10
                elif field == 'carbs_g':
                    result['carbs_g'] = 30
                elif field == 'confidence':
                    result['confidence'] = 0.5

        # Нормализация
        result['weight_g'] = max(1, min(5000, int(result['weight_g'])))
        result['calories'] = max(0, min(10000, int(result['calories'])))
        result['protein_g'] = max(0, round(float(result['protein_g']), 1))
        result['fat_g'] = max(0, round(float(result['fat_g']), 1))
        result['carbs_g'] = max(0, round(float(result['carbs_g']), 1))
        result['confidence'] = max(0, min(1, float(result['confidence'])))

        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}, raw: {raw_content}")
        return {"error": "invalid_json", "detail": str(e), "raw": raw_content}
    except Exception as e:
        logger.exception(f"ML service error: {e}")
        return {"error": "ml_error", "detail": str(e)}