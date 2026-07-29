# app/imaging.py
"""Единая точка регистрации декодеров изображений.

Камера iPhone по умолчанию снимает в HEIC. Safari транскодирует такие файлы
в JPEG не всегда: при выборе через «Файлы», во встроенных WebView (Telegram,
Instagram) и при широком accept="image/*" браузер отдаёт исходный HEIC.
Pillow «из коробки» этот контейнер не понимает — нужен pillow-heif.

Модуль импортируется всеми процессами, которые открывают изображения
(API, Celery-воркер, сканер штрих-кодов), чтобы регистрация опенера
не зависела от того, какой из них стартовал.
"""

import logging

logger = logging.getLogger(__name__)

try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
    HEIF_SUPPORTED = True
except Exception as exc:  # pragma: no cover - зависит от окружения
    HEIF_SUPPORTED = False
    logger.warning("pillow-heif is unavailable, HEIC images cannot be decoded: %s", exc)


# Форматы, которые Pillow должен опознать в загруженном файле.
# MPO — JPEG-контейнер с несколькими кадрами; так Pillow видит часть снимков
# с iPhone (портретный режим, серия). Декодируется как обычный JPEG.
SUPPORTED_INPUT_FORMATS = {"JPEG", "MPO", "PNG", "WEBP"}
if HEIF_SUPPORTED:
    SUPPORTED_INPUT_FORMATS |= {"HEIF", "HEIC"}

__all__ = ["HEIF_SUPPORTED", "SUPPORTED_INPUT_FORMATS"]
