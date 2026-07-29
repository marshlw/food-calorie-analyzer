# app/barcode_service.py
#
# Сканирование штрих-кода упаковки: декодирование кода с фото
# и получение названия/КБЖУ продукта из Open Food Facts.
#
# Декодер: zxing-cpp (устойчив к смазанным фото), фолбэк —
# cv2.barcode.BarcodeDetector (OpenCV уже в зависимостях).
# Ответы Open Food Facts кэшируются в Redis, чтобы не дёргать
# внешний API повторно (данные продуктов меняются редко).

import html
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from PIL import Image, ImageOps

from . import imaging  # noqa: F401 - регистрирует HEIC-декодер Pillow

from app.ml_service import get_http_client, get_redis_client

logger = logging.getLogger(__name__)

# Open Food Facts просит идентифицировать приложение в User-Agent
OFF_URL = "https://world.openfoodfacts.org/api/v2/product/{code}.json"
OFF_FIELDS = "code,product_name,product_name_ru,brands,quantity,nutriments,image_front_small_url"
OFF_USER_AGENT = "AI-Healthy/1.0 (food diary; contact: admin@ai-healthy.local)"

# v2: имена очищаются от HTML-сущностей (&quot; и т.п.) — старый кэш
# с «грязными» названиями инвалидируем сменой префикса ключа
CACHE_KEY = "off:product:v2:{code}"
CACHE_TTL = 7 * 24 * 3600          # найденный продукт — неделя
CACHE_MISS_TTL = 3600              # «не найдено» — час (базу OFF пополняют)

# Форматы розничных штрих-кодов еды (имена enum zxing-cpp)
RETAIL_FORMATS = {"EAN13", "EAN8", "UPCA", "UPCE"}


class BarcodeError(Exception):
    """Ошибка сценария сканирования; message показывается пользователю."""

    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class BarcodeProduct:
    barcode: str
    name: str
    brand: Optional[str]
    quantity: Optional[str]          # например «500 g» с упаковки
    calories_100g: float
    protein_100g: float
    fat_100g: float
    carbs_100g: float
    image_url: Optional[str]
    source: str                      # "openfoodfacts" | "cache"

    def as_dict(self) -> dict:
        return {
            "barcode": self.barcode,
            "name": self.name,
            "brand": self.brand,
            "quantity": self.quantity,
            "calories_100g": self.calories_100g,
            "protein_100g": self.protein_100g,
            "fat_100g": self.fat_100g,
            "carbs_100g": self.carbs_100g,
            "image_url": self.image_url,
            "source": self.source,
        }


# ===================== Декодирование штрих-кода =====================

def _decode_with_zxing(image: Image.Image) -> Optional[str]:
    try:
        import zxingcpp
    except ImportError:
        logger.warning("zxing-cpp is not installed; falling back to OpenCV")
        return None

    # Ошибка декодера (смазанное/битое фото) не должна ронять запрос —
    # просто считаем, что этот декодер код не нашёл
    try:
        results = zxingcpp.read_barcodes(image)
    except Exception as exc:
        logger.warning("zxing decode failed: %s", exc)
        return None

    for r in results:
        if getattr(r.format, "name", str(r.format)) in RETAIL_FORMATS and r.text:
            return r.text
    # Если нашёлся хоть какой-то код (например, QR) — вернём его,
    # валидация формата произойдёт на этапе поиска в OFF
    return results[0].text if results else None


def _decode_with_opencv(image: Image.Image) -> Optional[str]:
    try:
        import cv2
        import numpy as np
    except ImportError:
        return None

    # cv2.barcode может отсутствовать в сборке или бросать cv2.error
    # на «плохих» кадрах — это не повод отдавать 500
    try:
        frame = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
        detector = cv2.barcode.BarcodeDetector()
        ok, decoded, _, _ = detector.detectAndDecode(frame)
    except Exception as exc:
        logger.warning("OpenCV barcode decode failed: %s", exc)
        return None

    if ok:
        for text in decoded:
            if text:
                return text
    return None


def decode_barcode(image_path: str) -> str:
    """Извлекает штрих-код с фото. Пробует исходник и уменьшенные копии
    (на больших фото с телефона декодеры работают хуже)."""
    try:
        image = Image.open(image_path)
        image = ImageOps.exif_transpose(image)  # фото с телефона бывают повёрнуты
        image = image.convert("RGB")            # PNG c альфа-каналом и т.п.
    except Exception as exc:
        raise BarcodeError("Не удалось открыть изображение") from exc

    variants = [image]
    for max_side in (1600, 1000):
        if max(image.size) > max_side:
            scaled = image.copy()
            scaled.thumbnail((max_side, max_side))
            variants.append(scaled)

    for variant in variants:
        code = _decode_with_zxing(variant) or _decode_with_opencv(variant)
        if code:
            logger.info("Barcode decoded", extra={"code": code})
            return code

    raise BarcodeError(
        "Штрих-код не распознан. Сфотографируйте код крупнее, без бликов и размытия.",
        status_code=422,
    )


# ===================== Open Food Facts =====================

def _normalize_code(code: str) -> str:
    code = "".join(ch for ch in code.strip() if ch.isdigit())
    if not (8 <= len(code) <= 14):
        raise BarcodeError("Это не похоже на штрих-код продукта (EAN/UPC)")
    return code


def _parse_off_product(code: str, payload: dict) -> BarcodeProduct:
    product = payload.get("product") or {}
    nutriments = product.get("nutriments") or {}

    def clean(value) -> str:
        # OFF отдаёт названия с HTML-сущностями («&quot;Picnic&quot;»)
        return html.unescape(str(value or "")).strip()

    name = clean(product.get("product_name_ru")) or clean(product.get("product_name"))
    if not name:
        name = f"Продукт {code}"

    def n(key: str) -> float:
        try:
            return round(float(nutriments.get(key) or 0), 1)
        except (TypeError, ValueError):
            return 0.0

    calories = n("energy-kcal_100g")
    if not calories:
        # У части продуктов есть только энергия в кДж
        kj = n("energy_100g")
        calories = round(kj / 4.184, 1) if kj else 0.0

    return BarcodeProduct(
        barcode=code,
        name=name,
        brand=clean(product.get("brands")).split(",")[0].strip() or None,
        quantity=clean(product.get("quantity")) or None,
        calories_100g=calories,
        protein_100g=n("proteins_100g"),
        fat_100g=n("fat_100g"),
        carbs_100g=n("carbohydrates_100g"),
        image_url=product.get("image_front_small_url") or None,
        source="openfoodfacts",
    )


def lookup_product(code: str) -> BarcodeProduct:
    """Ищет продукт по штрих-коду: сперва в кэше Redis, затем в OFF."""
    code = _normalize_code(code)
    cache_key = CACHE_KEY.format(code=code)

    try:
        cached = get_redis_client().get(cache_key)
    except Exception as exc:
        logger.warning("Redis unavailable for barcode cache: %s", exc)
        cached = None

    if cached:
        data = json.loads(cached)
        if data.get("not_found"):
            raise BarcodeError(
                f"Блюда со штрих-кодом {code} нет в базе. Добавьте его вручную.",
                status_code=404,
            )
        return BarcodeProduct(**{**data, "source": "cache"})

    try:
        response = get_http_client().get(
            OFF_URL.format(code=code),
            params={"fields": OFF_FIELDS},
            headers={"User-Agent": OFF_USER_AGENT},
        )
    except httpx.HTTPError as exc:
        logger.warning("Open Food Facts request failed: %s", exc)
        raise BarcodeError(
            "База штрих-кодов временно недоступна, попробуйте позже",
            status_code=502,
        ) from exc

    def _cache(value: dict, ttl: int) -> None:
        try:
            get_redis_client().setex(cache_key, ttl, json.dumps(value, ensure_ascii=False))
        except Exception as exc:
            logger.warning("Unable to cache barcode product: %s", exc)

    # OFF отвечает 404 (v2) или status=0 для неизвестных кодов
    if response.status_code == 404 or (
        response.status_code == 200 and not (response.json() or {}).get("product")
    ):
        _cache({"not_found": True}, CACHE_MISS_TTL)
        raise BarcodeError(
            f"Блюда со штрих-кодом {code} нет в базе. Добавьте его вручную.",
            status_code=404,
        )

    if response.status_code != 200:
        logger.warning("Open Food Facts error: HTTP %s", response.status_code)
        raise BarcodeError(
            "База штрих-кодов временно недоступна, попробуйте позже",
            status_code=502,
        )

    product = _parse_off_product(code, response.json())
    payload = product.as_dict()
    payload.pop("source", None)
    _cache(payload, CACHE_TTL)
    return product


def scan_image(image_path: str) -> BarcodeProduct:
    """Полный сценарий: фото → штрих-код → продукт из Open Food Facts."""
    if not Path(image_path).exists():
        raise BarcodeError("Файл изображения не найден", status_code=500)
    code = decode_barcode(image_path)
    return lookup_product(code)
