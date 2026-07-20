import hashlib
import hmac
import time
from pathlib import Path
from PIL import Image
import magic
from typing import Tuple, Optional
from datetime import date
import os
import logging
logger = logging.getLogger(__name__)


# ==================== ПОДПИСАННЫЕ ССЫЛКИ НА ФОТО ====================

# Фото пользователей НЕ раздаются публичной статикой: каждая ссылка
# /uploads/<file>?exp=...&sig=... подписана HMAC(SECRET_KEY) и живёт
# ограниченное время. Без валидной подписи файл не отдаётся.

def _upload_signature(filename: str, exp: int) -> str:
    from .config import settings
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        f"{filename}:{exp}".encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def signed_upload_url(path_or_name: str, ttl: Optional[int] = None) -> str:
    """Подписанный URL для файла из UPLOAD_DIR (по имени файла)."""
    from .config import settings
    name = Path(path_or_name).name
    exp = int(time.time()) + int(ttl or settings.UPLOAD_URL_TTL)
    return f"/uploads/{name}?exp={exp}&sig={_upload_signature(name, exp)}"


def verify_upload_signature(filename: str, exp: int, sig: str) -> bool:
    """Проверка подписи и срока действия ссылки на файл."""
    if exp < time.time():
        return False
    return hmac.compare_digest(_upload_signature(filename, exp), sig or "")


# ==================== BMR / НОРМА КАЛОРИЙ ====================

# Коэффициенты физической активности (множитель к BMR -> TDEE).
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}


def calc_age(birth_date: Optional[date]) -> Optional[int]:
    """Полных лет на сегодня."""
    if not birth_date:
        return None
    today = date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def calc_bmr(weight_kg: Optional[float], height_cm: Optional[float],
             age: Optional[int], sex: Optional[str]) -> Optional[float]:
    """Базовый обмен веществ по формуле Миффлина-Сан-Жеора.
    Возвращает None, если данных не хватает."""
    if not all([weight_kg, height_cm, age, sex]):
        return None
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return round(base + (5 if sex == "male" else -161), 1)


def calc_daily_calorie_target(bmr: Optional[float],
                              activity_level: Optional[str]) -> Optional[float]:
    """Дневная норма калорий (TDEE) = BMR * коэффициент активности."""
    if bmr is None:
        return None
    return round(bmr * ACTIVITY_FACTORS.get(activity_level or "sedentary", 1.2))


# Распределение суточной нормы калорий по макронутриентам (доля от ккал).
# 30% белки / 30% жиры / 40% углеводы — сбалансированный дефолт.
MACRO_SPLIT = {"protein": 0.30, "fat": 0.30, "carbs": 0.40}
# Калорийность 1 г макронутриента.
KCAL_PER_GRAM = {"protein": 4.0, "fat": 9.0, "carbs": 4.0}


def calc_macro_targets(calorie_target: Optional[float]) -> dict:
    """Норма белков/жиров/углеводов (в граммах) из суточной нормы калорий —
    по аналогии с нормой калорий. Возвращает None-значения, если калорий нет."""
    if not calorie_target:
        return {"protein_g": None, "fat_g": None, "carbs_g": None}
    return {
        "protein_g": round(calorie_target * MACRO_SPLIT["protein"] / KCAL_PER_GRAM["protein"]),
        "fat_g": round(calorie_target * MACRO_SPLIT["fat"] / KCAL_PER_GRAM["fat"]),
        "carbs_g": round(calorie_target * MACRO_SPLIT["carbs"] / KCAL_PER_GRAM["carbs"]),
    }


# ==================== НОРМА ВОДЫ ====================

# Объём одного стакана (мл) — единица учёта в трекере воды.
GLASS_ML = 250

# Норма воды считается как «мл на кг массы тела». Базовая медицинская норма
# для взрослого ~30 мл/кг; с ростом активности потребность в жидкости выше,
# поэтому коэффициент растёт по тем же уровням, что и активность для калорий.
WATER_ML_PER_KG = {
    "sedentary": 30,
    "light": 32,
    "moderate": 35,
    "active": 38,
    "very_active": 40,
}


def calc_water_target(weight_kg: Optional[float],
                      activity_level: Optional[str]) -> Optional[float]:
    """Суточная норма воды (мл) = вес * (мл/кг по уровню активности).
    Возвращает None, если неизвестен вес. Рост/возраст на питьевую норму
    напрямую не влияют — определяющий фактор это масса тела и активность."""
    if not weight_kg:
        return None
    ml_per_kg = WATER_ML_PER_KG.get(activity_level or "sedentary", 30)
    return round(weight_kg * ml_per_kg)
from PIL import Image
import hashlib
import magic
from pathlib import Path
import json

def compute_file_hash(file_path: str, algorithm: str = "sha256") -> str:
    """Вычисляет хэш файла"""
    hash_func = hashlib.new(algorithm)
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()


def validate_image_file(file_path: str) -> bool:
    """Проверяет что файл действительно является изображением"""
    try:
        mime = magic.from_file(file_path, mime=True)
        return mime.startswith('image/')
    except:
        return False


def process_image(
        input_path: str,
        max_size: Tuple[int, int] = (1024, 1024),
        quality: int = 85,
        output_path: Optional[str] = None
) -> str:
    """
    Обрабатывает изображение:
    - Конвертирует в RGB
    - Удаляет EXIF
    - Ресайзит с сохранением пропорций
    - Сжимает JPEG
    Возвращает путь к обработанному файлу
    """
    if output_path is None:
        output_path = input_path

    try:
        with Image.open(input_path) as img:
            # Конвертируем в RGB если нужно
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")

            # Удаляем EXIF (создаем новое изображение без метаданных)
            data = list(img.getdata())
            img_without_exif = Image.new(img.mode, img.size)
            img_without_exif.putdata(data)

            # Ресайзим с сохранением пропорций
            img_without_exif.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Сохраняем с оптимизацией
            img_without_exif.save(
                output_path,
                "JPEG",
                quality=quality,
                optimize=True,
                progressive=True,
                subsampling=0  # лучшее качество
            )

        return output_path

    except Exception as e:
        logger.error(f"Image processing failed: {e}")
        # Если обработка не удалась, возвращаем оригинал
        return input_path


def generate_thumbnail(
        image_path: str,
        thumbnail_size: Tuple[int, int] = (200, 200),
        output_path: Optional[str] = None
) -> str:
    """Генерирует миниатюру"""
    if output_path is None:
        output_path = str(Path(image_path).with_name(
            f"thumb_{Path(image_path).name}"
        ))

    try:
        with Image.open(image_path) as img:
            img.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=75, optimize=True)
        return output_path
    except Exception as e:
        logger.error(f"Thumbnail generation failed: {e}")
        return ""