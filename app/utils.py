import hashlib
from pathlib import Path
from PIL import Image
import magic
from typing import Tuple, Optional
import os
import logging
logger = logging.getLogger(__name__)
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