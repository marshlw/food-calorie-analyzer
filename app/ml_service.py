import asyncio
import json
import logging
import re
import time
import hashlib
import base64
import threading
from pathlib import Path
from typing import Optional, Any, List, Dict
from openai import OpenAI
import redis
import httpx
from PIL import Image
from pydantic import BaseModel, Field, StrictInt, StrictFloat, StrictStr, conlist, validator, ValidationError

from .config import settings
from . import models
from .database import SessionLocal

try:
    from .food_map import SYNONYMS
except Exception:  # словарь синонимов опционален
    SYNONYMS = {}

# Ориентировочные нутриенты на 100 г по типу ингредиента.
# Используются как запасной вариант, когда продукт не найден в таблице products,
# чтобы КБЖУ не оставались нулевыми. AI стабильно возвращает поле type.
TYPE_KBJU_PER_100G = {
    "protein":   {"calories": 165, "protein_g": 23.0, "fat_g": 7.0,  "carbs_g": 1.0},
    "carb":      {"calories": 180, "protein_g": 5.0,  "fat_g": 2.0,  "carbs_g": 35.0},
    "fat":       {"calories": 380, "protein_g": 3.0,  "fat_g": 40.0, "carbs_g": 5.0},
    "vegetable": {"calories": 35,  "protein_g": 2.0,  "fat_g": 0.3,  "carbs_g": 6.0},
    "unknown":   {"calories": 120, "protein_g": 5.0,  "fat_g": 4.0,  "carbs_g": 15.0},
}

logger = logging.getLogger(__name__)

# ================= CONFIG / RESOURCES =================

UPLOAD_DIR = Path(settings.UPLOAD_DIR)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROMPT_VERSION = "v12"  # инвалидируем старый кеш

PROMPT = """
Проанализируй фотографию еды.

Верни строго JSON:

{
  "food":"название блюда",
  "ingredients":[
    {
      "name":"ингредиент",
      "type":"protein|carb|fat|vegetable"
    }
  ],
  "weight_g":250,
  "confidence":0.95
}

Правила:

- ingredients минимум 1 элемент
- максимум 6 ингредиентов
- weight_g от 50 до 1500
- confidence от 0 до 1
- если не уверен, сделай предположение
- отвечай только JSON
"""

DEFAULT_FALLBACK = {
    "food": "unknown",
    "weight_g": 200,
    "calories": 200,
    "protein_g": 10,
    "fat_g": 10,
    "carbs_g": 20,
    "confidence": 0.0,
    "ingredients": [],
}

MODEL_CANDIDATES = [
    "gemini-2.5-flash-image",
    "gemini-3.1-flash-image-preview",
    "gemini-3-pro-image-preview",
]

PROVIDER_FAILURE_THRESHOLD = 3
PROVIDER_COOLDOWN_SECONDS = 300

_resource_lock = threading.RLock()
_http_client: Optional[httpx.Client] = None
_redis_client: Optional[redis.Redis] = None
_providers: Optional[List["BaseProvider"]] = None
_lock = threading.Lock()
_last_calls: dict[str, float] = {}


def get_http_client(timeout_seconds: Optional[float] = None) -> httpx.Client:
    """Thread-safe lazy HTTP client with optional custom timeout."""
    global _http_client
    with _resource_lock:
        if _http_client is None:
            default_timeout = getattr(settings, "MODEL_TIMEOUT_SECONDS", 30)
            _http_client = httpx.Client(
                timeout=httpx.Timeout(default_timeout, connect=5.0),
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        if timeout_seconds and timeout_seconds != getattr(settings, "MODEL_TIMEOUT_SECONDS", 30):
            return httpx.Client(
                timeout=httpx.Timeout(timeout_seconds, connect=5.0),
                limits=httpx.Limits(max_connections=5, max_keepalive_connections=2),
            )
        return _http_client


def close_http_client() -> None:
    global _http_client
    with _resource_lock:
        if _http_client is not None:
            try:
                _http_client.close()
            except Exception as exc:
                logger.warning("Failed to close http client: %s", exc)
            finally:
                _http_client = None


def get_redis_client() -> redis.Redis:
    """Thread-safe Redis connection getter."""
    global _redis_client
    with _resource_lock:
        if _redis_client is None:
            _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        return _redis_client


def close_redis_client() -> None:
    global _redis_client
    with _resource_lock:
        if _redis_client is not None:
            try:
                _redis_client.close()
            except Exception as exc:
                logger.warning("Failed to close redis client: %s", exc)
            finally:
                _redis_client = None


class ProviderError(Exception):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = PROVIDER_FAILURE_THRESHOLD, cooldown_seconds: int = PROVIDER_COOLDOWN_SECONDS):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.failure_count = 0
        self.disabled_until = 0.0
        self._lock = threading.Lock()

    def record_failure(self) -> None:
        with self._lock:
            self.failure_count += 1
            if self.failure_count >= self.failure_threshold:
                self.disabled_until = time.time() + self.cooldown_seconds
                logger.warning(
                    "Circuit breaker open: disabled for %.1fs", self.cooldown_seconds,
                    extra={"circuit_breaker": True, "failure_count": self.failure_count},
                )

    def record_success(self) -> None:
        with self._lock:
            self.failure_count = 0
            self.disabled_until = 0.0

    def is_available(self) -> bool:
        with self._lock:
            if self.disabled_until and time.time() < self.disabled_until:
                return False
            if self.disabled_until and time.time() >= self.disabled_until:
                self.failure_count = 0
                self.disabled_until = 0.0
            return True


class IngredientItem(BaseModel):
    name: StrictStr
    type: StrictStr = Field("unknown")
    weight_g: StrictInt = Field(0, ge=0)

    @validator("name", pre=True)
    def normalize_name(cls, value: Any) -> str:
        return str(value).strip().lower()

    @validator("type", pre=True)
    def normalize_type(cls, value: Any) -> str:
        value = str(value or "unknown").strip().lower()
        return value if value in {"protein", "carb", "fat", "vegetable"} else "unknown"

    @validator("weight_g", pre=True)
    def normalize_weight(cls, value: Any) -> int:
        try:
            normalized = int(value)
        except Exception:
            normalized = 0
        return max(0, min(2000, normalized))

    class Config:
        extra = "ignore"


class AnalysisResult(BaseModel):
    food: StrictStr
    ingredients: conlist(IngredientItem, max_length=6) = Field(default_factory=list)
    weight_g: StrictInt = Field(..., ge=50, le=2000)
    confidence: StrictFloat = Field(..., ge=0.0, le=1.0)

    @validator("food", pre=True)
    def normalize_food(cls, value: Any) -> str:
        value = str(value or "").strip()
        if not value:
            raise ValueError("food is required")
        return value

    @validator("confidence", pre=True)
    def normalize_confidence(cls, value: Any) -> float:
        try:
            return float(value)
        except Exception:
            raise ValueError("confidence must be a float")

    class Config:
        extra = "ignore"


class BaseProvider:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name
        self.circuit_breaker = CircuitBreaker()

    def available(self) -> bool:
        return self.circuit_breaker.is_available()

    def call(self, prompt: str, image_path: Optional[str]) -> Optional[str]:
        if not self.available():
            logger.warning(
                "Provider %s is temporarily disabled by circuit breaker",
                self.name,
                extra={"provider": self.name, "source": "circuit_breaker"},
            )
            return None

        for attempt in range(1, settings.MODEL_RETRY_ATTEMPTS + 1):
            start_time = time.perf_counter()
            try:
                raw_text = self._execute(prompt, image_path)
                latency = time.perf_counter() - start_time
                if raw_text and raw_text.strip():
                    self.circuit_breaker.record_success()
                    logger.info(
                        "Provider returned response",
                        extra={
                            "provider": self.name,
                            "attempt": attempt,
                            "latency": round(latency, 3),
                        },
                    )
                    return raw_text
                raise ProviderError("Empty response")
            except Exception as exc:
                latency = time.perf_counter() - start_time
                self.circuit_breaker.record_failure()
                logger.warning(
                    "Provider %s attempt %s failed",
                    self.name,
                    attempt,
                    extra={
                        "provider": self.name,
                        "attempt": attempt,
                        "latency": round(latency, 3),
                        "error": str(exc),
                    },
                )
                if is_quota_error(exc):
                    break
                if attempt < settings.MODEL_RETRY_ATTEMPTS:
                    time.sleep(_prepare_backoff(attempt))
        return None

    def _execute(self, prompt: str, image_path: Optional[str]) -> str:
        raise NotImplementedError


class GeminiProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("gemini")
        self.model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash-image")
        self._client: Optional[Any] = None

    def _ensure_client(self) -> None:
        if self._client is None:
            if not settings.GEMINI_API_KEY:
                raise ProviderError("Gemini API key is missing")
            from google import genai

            self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
            logger.info("Gemini client initialized", extra={"provider": "gemini"})

    def _execute(self, prompt: str, image_path: Optional[str]) -> str:
        try:
            self._ensure_client()
        except ProviderError as e:
            logger.error("Gemini initialization failed: %s", str(e))
            raise

        contents = [prompt]
        if image_path:
            with Image.open(image_path) as src:
                img = src.convert("RGB")
                contents.append(img)
        response = self._client.models.generate_content(
            model=self.model,
            contents=contents,
        )
        text = getattr(response, "text", None)
        if not text or not str(text).strip():
            raise ProviderError("Gemini returned empty response")
        return str(text)


class DeepSeekProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("deepseek")

    def _execute(self, prompt: str, image_path: Optional[str]) -> str:
        if not settings.DEEPSEEK_API_KEY:
            raise ProviderError("DeepSeek API key is missing")
        if not settings.DEEPSEEK_VISION_API_URL:
            raise ProviderError("DeepSeek API URL is missing")
        if not image_path:
            raise ProviderError("Image path is required for DeepSeek")

        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise ProviderError(f"Failed to read/encode image: {e}")

        ext = Path(image_path).suffix.lower()
        image_type = "jpeg" if ext in [".jpg", ".jpeg"] else "png" if ext == ".png" else "jpeg"

        payload = {
            "model": settings.DEEPSEEK_VISION_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/{image_type};base64,{image_data}"
                            },
                        },
                    ],
                }
            ],
            "temperature": 0.0,
            "max_tokens": 500,
        }

        headers = {
            "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
        }

        try:
            response = get_http_client().post(
                settings.DEEPSEEK_VISION_API_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            error_msg = f"DeepSeek API error {e.status_code}"
            try:
                error_body = e.response.text
                error_msg += f": {error_body}"
            except Exception:
                pass
            raise ProviderError(error_msg)

        data = response.json()
        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise ProviderError("DeepSeek returned no choices")

        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        text = message.get("content") if isinstance(message, dict) else None
        if not text or not str(text).strip():
            raise ProviderError("DeepSeek returned empty content")
        return str(text)


class OllamaProvider(BaseProvider):
    def __init__(self) -> None:
        super().__init__("ollama")
        self.model_name = getattr(settings, "OLLAMA_MODEL", "llava:7b")
        self.host = getattr(settings, "OLLAMA_HOST", "http://ollama:11434")

    def _execute(self, prompt: str, image_path: Optional[str]) -> str:
        if not image_path:
            raise ProviderError("Image path is required for Ollama")

        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")
        except Exception as e:
            raise ProviderError(f"Failed to read/encode image for Ollama: {e}")

        payload = {
            "model": self.model_name,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False,
            "options": {"temperature": 0.0},
        }

        try:
            endpoint = f"{self.host.rstrip('/')}/api/generate"
            logger.info("Sending request to Ollama", extra={"model": self.model_name, "endpoint": endpoint})
            response = get_http_client().post(endpoint, json=payload)
            response.raise_for_status()
        except httpx.ConnectError as e:
            raise ProviderError(f"Failed to connect to Ollama at {self.host}: {e}")
        except httpx.TimeoutException as e:
            raise ProviderError(f"Ollama request timed out: {e}")
        except httpx.HTTPStatusError as e:
            error_msg = f"Ollama returned error {e.status_code}"
            try:
                error_body = e.response.text
                error_msg += f": {error_body}"
            except Exception:
                pass
            raise ProviderError(error_msg)

        data = response.json()
        text = data.get("response")
        if not text or not str(text).strip():
            raise ProviderError("Ollama returned empty response")
        return str(text)


# ================= YANDEX PROVIDER (MULTIMODAL) =================
class YandexProvider(BaseProvider):

    def __init__(self):
        super().__init__("yandex")

        self.api_key = settings.YANDEX_API_KEY
        self.folder_id = settings.YANDEX_FOLDER_ID
        self.model = settings.YANDEX_VISION_MODEL

        self._client = None

    def _get_client(self):

        if self._client is None:

            if not self.api_key:
                raise ProviderError(
                    "YANDEX_API_KEY missing"
                )

            if not self.folder_id:
                raise ProviderError(
                    "YANDEX_FOLDER_ID missing"
                )

            self._client = OpenAI(
                api_key=self.api_key,
                base_url="https://ai.api.cloud.yandex.net/v1",
                project=self.folder_id,
            )

        return self._client

    def _execute(
        self,
        prompt: str,
        image_path: Optional[str]
    ) -> str:

        if not image_path:
            raise ProviderError("Image required")

        client = self._get_client()

        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(
                f.read()
            ).decode("utf-8")

        try:

            response = client.responses.create(
                model=f"gpt://{self.folder_id}/{self.model}",
                temperature=0.0,
                max_output_tokens=2000,
                reasoning={
                    "effort": "none"
                },
                instructions="""
Ты эксперт по анализу еды.

Верни только JSON.

{
  "food":"...",
  "ingredients":[
    {
      "name":"...",
      "type":"protein|carb|fat|vegetable"
    }
  ],
  "weight_g":250,
  "confidence":0.95
}

Никакого markdown.
Только JSON.
""",

                input=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": prompt,
                            },

                            # ВАЖНО
                            {
                                "type": "input_image",
                                "image_url": (
                                    f"data:image/jpeg;base64,{image_b64}"
                                )
                            }
                        ]
                    }
                ]
            )

        except Exception as e:

            logger.exception(
                "YANDEX REQUEST FAILED"
            )

            raise ProviderError(
                f"Yandex request failed: {repr(e)}"
            )

        # ==========================
        # Логируем ответ полностью
        # ==========================

        try:

            logger.info(
                "YANDEX RAW RESPONSE:\n%s",
                response.model_dump_json(
                    indent=2
                )
            )
            dump = response.model_dump()

            logger.error(
                "YANDEX STATUS=%s VALID=%s",
                dump.get("status"),
                dump.get("valid")
            )

            logger.error(
                "YANDEX ERROR=%s",
                json.dumps(
                    dump.get("error"),
                    ensure_ascii=False,
                    indent=2
                )
            )

            logger.error(
                "YANDEX INCOMPLETE=%s",
                json.dumps(
                    dump.get("incomplete_details"),
                    ensure_ascii=False,
                    indent=2
                )
            )

            logger.error(
                "YANDEX OUTPUT=%s",
                json.dumps(
                    dump.get("output"),
                    ensure_ascii=False,
                    indent=2
                )[:5000]
            )

        except Exception:

            logger.info(
                "YANDEX RESPONSE OBJECT:\n%s",
                repr(response)
            )

        # ==========================
        # Новый API
        # ==========================

        try:

            text = response.output_text

            if text and text.strip():

                logger.info(
                    "YANDEX OUTPUT_TEXT:\n%s",
                    text[:2000]
                )

                return text

        except Exception as e:

            logger.warning(
                "output_text parse failed: %s",
                repr(e)
            )

        # ==========================
        # Фоллбек-парсер
        # ==========================

        try:

            if hasattr(response, "output"):

                for item in response.output:

                    if not hasattr(item, "content"):
                        continue

                    for content in item.content:

                        text = getattr(
                            content,
                            "text",
                            None
                        )

                        if text and text.strip():

                            logger.info(
                                "YANDEX OUTPUT CONTENT:\n%s",
                                text[:2000]
                            )

                            return text

        except Exception as e:

            logger.warning(
                "output content parse failed: %s",
                repr(e)
            )

        # ==========================
        # Не смогли распарсить
        # ==========================

        try:

            dump = response.model_dump()

            raise ProviderError(
                "Unknown response format:\n"
                + json.dumps(
                    dump,
                    ensure_ascii=False,
                    indent=2
                )[:5000]
            )

        except Exception as e:

            raise ProviderError(
                f"Failed to parse Yandex response: {repr(e)}"
            )


# ================= END YANDEX PROVIDER =================


def get_providers() -> List[BaseProvider]:
    global _providers
    with _resource_lock:
        if _providers is None:
            _providers = [GeminiProvider(), DeepSeekProvider(), OllamaProvider(), YandexProvider()]
        return _providers


def _get_provider_by_name(name: str) -> BaseProvider:
    for provider in get_providers():
        if provider.name == name:
            return provider
    raise ProviderError(f"Unknown provider: {name}")


def call_gemini(prompt: str, image_path: Optional[str] = None) -> Optional[str]:
    provider = _get_provider_by_name("gemini")
    return provider.call(prompt, image_path)


def call_deepseek_vision(prompt: str, image_path: Optional[str] = None) -> Optional[str]:
    provider = _get_provider_by_name("deepseek")
    return provider.call(prompt, image_path)


def call_ollama_vision(prompt: str, image_path: Optional[str] = None) -> Optional[str]:
    provider = _get_provider_by_name("ollama")
    return provider.call(prompt, image_path)


def call_yandex(prompt: str, image_path: Optional[str] = None) -> Optional[str]:
    provider = _get_provider_by_name("yandex")
    return provider.call(prompt, image_path)


def get_provider_callables() -> List[tuple[str, Any]]:
    provider_map = {
        "gemini": "call_gemini",
        "deepseek": "call_deepseek_vision",
        "ollama": "call_ollama_vision",
        "yandex": "call_yandex",
    }
    preferred = settings.MODEL_PROVIDER.lower()
    if preferred not in provider_map:
        logger.warning(
            "Unknown MODEL_PROVIDER '%s', using fallback order: %s",
            preferred,
            ", ".join(provider_map),
        )
        preferred = "yandex"

    ordered = [preferred] + [name for name in provider_map if name != preferred]
    return [(name, provider_map[name]) for name in ordered]


def rate_limit(key: str, min_interval: float = 1.2):
    """Thread-safe rate limiter."""
    wait = 0.0
    with _lock:
        now = time.time()
        diff = now - _last_calls.get(key, 0.0)
        if diff < min_interval:
            wait = min_interval - diff
            _last_calls[key] = now + wait
        else:
            _last_calls[key] = now
    if wait > 0:
        time.sleep(wait)


def extract_json(text: Optional[str]) -> Optional[dict]:
    """Extract JSON from text, handling control characters and various formats."""
    if not text:
        return None

    text = re.sub(r"[\x00-\x1f\x7f]+", "", str(text)).strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        try:
            return json.loads(code_block.group(1).strip())
        except Exception:
            pass

    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except Exception:
            pass

    return None


def validate_response(data: Optional[dict]) -> bool:
    if not isinstance(data, dict):
        return False
    try:
        AnalysisResult(**data)
        return True
    except ValidationError:
        return False


def _get_cached_result(cache_key: str) -> Optional[dict]:
    try:
        redis_conn = get_redis_client()
        cached = redis_conn.get(cache_key)
        if not cached:
            return None
        cached_data = json.loads(cached)
        if isinstance(cached_data, dict):
            return cached_data
    except redis.RedisError as exc:
        logger.warning("Redis cache read failed", extra={"error": str(exc), "cache_key": cache_key})
    except json.JSONDecodeError:
        logger.warning("Corrupt cached result ignored", extra={"cache_key": cache_key})
    return None


def _set_cached_result(cache_key: str, payload: dict) -> None:
    try:
        redis_conn = get_redis_client()
        redis_conn.setex(cache_key, settings.CACHE_TTL, json.dumps(payload, ensure_ascii=False))
    except Exception as exc:
        logger.warning("Redis cache write failed", extra={"error": str(exc), "cache_key": cache_key})


def is_quota_error(e: Exception) -> bool:
    """Check if exception is a quota/rate limit error."""
    msg = str(e)
    return (
        "429" in msg
        or "RESOURCE_EXHAUSTED" in msg
        or "quota" in msg.lower()
        or "too many requests" in msg.lower()
    )


def _prepare_backoff(attempt: int) -> float:
    return max(0.5, settings.MODEL_BACKOFF_FACTOR * attempt)


def parse_model_response(raw_text: Optional[str]) -> Optional[dict]:
    """
    Парсит ответ модели. Сначала строгая валидация через AnalysisResult.
    При неудаче – мягкое восстановление полей.
    """
    if not raw_text:
        return None

    data = extract_json(raw_text)
    if not isinstance(data, dict):
        return None

    # Попытка 1: строгая валидация
    try:
        parsed = AnalysisResult(**data)
        return parsed.dict()
    except ValidationError as e:
        logger.warning("Strict validation failed, trying soft recovery: %s", e)

    # Попытка 2: мягкое восстановление
    try:
        food = str(data.get("food", "")).strip()
        if not food:
            food = "unknown"

        # confidence
        conf = data.get("confidence", 0.0)
        try:
            confidence = float(conf)
        except (ValueError, TypeError):
            confidence = 0.0

        # weight_g
        w = data.get("weight_g", 200)
        try:
            weight_g = int(w)
        except (ValueError, TypeError):
            weight_g = 200

        # ingredients
        ingredients_raw = data.get("ingredients", [])
        ingredients = []
        if isinstance(ingredients_raw, list):
            for ing in ingredients_raw[:6]:
                if isinstance(ing, dict):
                    name = str(ing.get("name", "")).strip().lower()
                    ing_type = str(ing.get("type", "unknown")).strip().lower()
                    if ing_type not in {"protein", "carb", "fat", "vegetable"}:
                        ing_type = "unknown"
                    ingredients.append({
                        "name": name,
                        "type": ing_type,
                        "weight_g": 0   # будет перераспределён позже в analyze_image_sync
                    })

        return {
            "food": food,
            "confidence": round(confidence, 3),
            "weight_g": weight_g,
            "ingredients": ingredients,
        }
    except Exception as e:
        logger.warning("Soft recovery also failed: %s", e)
        return None


def preprocess(path: str) -> str:
    """Preprocess image: resize and compress."""
    try:
        Image.MAX_IMAGE_PIXELS = getattr(settings, "MAX_IMAGE_PIXELS", 100000000)
        with Image.open(path) as src:
            img = src.convert("RGB")
            max_size = getattr(settings, "MAX_IMAGE_SIZE", 1600)
            quality = getattr(settings, "IMAGE_QUALITY", 90)
            img.thumbnail((max_size, max_size))
            out = UPLOAD_DIR / f"p_{Path(path).stem}.jpg"
            img.save(out, "JPEG", quality=quality, optimize=True)
            return str(out)
    except Exception as e:
        logger.warning(f"Image preprocess error: {e}")
        return path


def get_hash(path: str) -> str:
    """Calculate SHA256 hash of file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_product_name(name: str) -> str:
    """Нормализует имя ингредиента: нижний регистр + словарь синонимов."""
    key = (name or "").lower().strip()
    return SYNONYMS.get(key, key)


def get_product(session, name: str):
    """Get product by normalized name (с учётом синонимов)."""
    norm = normalize_product_name(name)
    if not norm:
        return None
    return (
        session.query(models.Product)
        .filter(models.Product.name == norm)
        .first()
    )


def _estimate_by_type(ing_type: str) -> dict:
    """Оценка нутриентов на 100 г по типу ингредиента."""
    return TYPE_KBJU_PER_100G.get((ing_type or "unknown").lower(), TYPE_KBJU_PER_100G["unknown"])


def calc_kbju(session, ingredients: List[dict]) -> dict:
    """Суммарные КБЖУ по ингредиентам.

    Для каждого ингредиента сначала пытаемся взять точные данные из таблицы
    products; если совпадения нет (или таблица недоступна) — используем оценку
    по типу ингредиента, чтобы итог не был нулевым. Ошибки по отдельному
    ингредиенту не обнуляют весь расчёт.
    """
    total = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}

    for ing in ingredients:
        try:
            weight = int(ing.get("weight_g", 50) or 50)
            k = weight / 100.0

            product = None
            try:
                product = get_product(session, ing.get("name"))
            except Exception as exc:
                # таблица products может отсутствовать/быть недоступной — не падаем
                logger.warning("Product lookup failed, falling back to type estimate", extra={"error": str(exc)})

            if product is not None:
                per100 = {
                    "calories": float(product.calories),
                    "protein_g": float(product.protein),
                    "fat_g": float(product.fat),
                    "carbs_g": float(product.carbs),
                }
            else:
                per100 = _estimate_by_type(ing.get("type"))

            for key in total:
                total[key] += per100[key] * k
        except Exception as exc:
            logger.warning("Skipping ingredient in KBJU calc", extra={"error": str(exc), "ingredient": ing})
            continue

    return {key: round(value, 1) for key, value in total.items()}


def analyze_image_sync(path: str) -> dict:
    """Synchronous image analysis with fallback routing."""
    start_time = time.perf_counter()
    session = SessionLocal()
    models_tried: List[str] = []

    try:
        cache_key = f"{settings.CACHE_PREFIX}:{PROMPT_VERSION}:{get_hash(path)}"
        cached_data = _get_cached_result(cache_key)
        if cached_data:
            cached_data["source"] = "cache"
            cached_data["models_tried"] = cached_data.get("models_tried", [])
            cached_data["processing_time_sec"] = round(time.perf_counter() - start_time, 3)
            logger.info("📦 Cache hit", extra={"source": cached_data.get("source")})
            return cached_data

        img = preprocess(path)
        source = "fallback"
        result: Optional[dict] = None

        for provider_name, provider_function_name in get_provider_callables():
            models_tried.append(provider_name)
            logger.info("Trying provider", extra={"provider": provider_name, "models_tried": models_tried})
            provider_callable = globals().get(provider_function_name)
            if not callable(provider_callable):
                logger.warning("Provider callable missing", extra={"provider": provider_name})
                continue
            raw_text = provider_callable(PROMPT, img)
            parsed = parse_model_response(raw_text)
            if parsed:
                result = parsed
                source = provider_name
                break

        if result is None:
            logger.warning("All providers failed, returning fallback", extra={"models_tried": models_tried})
            result = DEFAULT_FALLBACK.copy()
        else:
            ingredients = result.get("ingredients", [])
            total_weight = int(result.get("weight_g", 200))
            if ingredients:
                per_item = max(20, total_weight // max(1, len(ingredients)))
                for ing in ingredients:
                    ing["weight_g"] = per_item
            try:
                kbju = calc_kbju(session, ingredients)
            except Exception as exc:
                logger.warning("KBJU lookup failed, using zeros", extra={"error": str(exc)})
                kbju = {"calories": 0.0, "protein_g": 0.0, "fat_g": 0.0, "carbs_g": 0.0}
            result = {
                "food": result.get("food", "unknown"),
                "confidence": round(float(result.get("confidence", 0.0)), 3),
                "weight_g": total_weight,
                "ingredients": ingredients,
                **kbju,
            }

        result["source"] = source
        result["models_tried"] = models_tried
        result["processing_time_sec"] = round(time.perf_counter() - start_time, 3)

        # Сохраняем в кэш без временной метки, но с source
        cache_payload = {k: v for k, v in result.items() if k != "processing_time_sec"}
        _set_cached_result(cache_key, cache_payload)

        logger.info("✅ Analysis completed successfully", extra={"source": source, "models_tried": models_tried})
        return result

    except FileNotFoundError as exc:
        logger.warning("Image file not found", extra={"path": path, "error": str(exc)})
        return {
            "error": "Image file not found",
            "source": "error",
            "models_tried": models_tried,
            "processing_time_sec": round(time.perf_counter() - start_time, 3),
        }
    except Exception as exc:
        logger.exception("Unexpected analysis error", exc_info=exc)
        return {
            **DEFAULT_FALLBACK,
            "source": "fallback",
            "models_tried": models_tried,
            "processing_time_sec": round(time.perf_counter() - start_time, 3),
        }
    finally:
        session.close()


async def analyze_image_async(path: str) -> dict:
    return await asyncio.to_thread(analyze_image_sync, path)


def analyze_image(path: str) -> dict:
    return analyze_image_sync(path)


def update_model(model_name: str) -> None:
    """Update dynamic provider models (best-effort)."""
    try:
        for p in get_providers():
            if hasattr(p, "model_name"):
                setattr(p, "model_name", model_name)
            if hasattr(p, "model"):
                try:
                    setattr(p, "model", model_name)
                except Exception:
                    pass
        logger.info("Model updated for providers", extra={"model_name": model_name})
    except Exception as exc:
        logger.warning("Failed to update model on providers", extra={"error": str(exc)})