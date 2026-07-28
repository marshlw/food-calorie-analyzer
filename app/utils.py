import hashlib
import hmac
import time
from pathlib import Path
from PIL import Image
import magic
from typing import Tuple, Optional
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


# ==================== BMR / НОРМЫ КБЖУ ====================

# Расчёт норм живёт в app/nutrition.py — там он учитывает цель пользователя
# (похудение / поддержание / набор), безопасные ограничители и прогноз сроков.
# Здесь оставлены реэкспорты, чтобы старые импорты `utils.calc_bmr` и
# `utils.GLASS_ML` продолжали работать.

from .nutrition import (  # noqa: E402,F401
    ACTIVITY_FACTORS,
    GLASS_ML,
    KCAL_PER_GRAM,
    WATER_ML_PER_KG,
    build_plan,
    calc_age,
    calc_bmi,
    calc_bmr,
    calc_macro_targets,
    calc_tdee,
    calc_water_target,
)


def calc_daily_calorie_target(bmr: Optional[float],
                              activity_level: Optional[str]) -> Optional[float]:
    """Устарело: норма поддержания веса (TDEE) без учёта цели.
    Оставлено для обратной совместимости — используйте nutrition.build_plan."""
    return calc_tdee(bmr, activity_level)


# ==================== РАБОТА С ИЗОБРАЖЕНИЯМИ ====================

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