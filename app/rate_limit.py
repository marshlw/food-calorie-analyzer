# app/rate_limit.py
"""Rate limiting: защита от брутфорса auth-эндпоинтов и дневной лимит AI-анализа.

Счётчики хранятся в Redis (фиксированное окно, атомарный INCR).
При недоступности Redis — graceful fallback на in-memory хранилище,
чтобы API не падал (лимиты тогда действуют в рамках одного процесса).
"""

import logging
import threading
import time
from datetime import date, datetime, timedelta
from typing import Dict, Tuple

from fastapi import HTTPException, Request

from .config import settings

logger = logging.getLogger(__name__)

_PREFIX = "ratelimit:"

# ---------- in-memory fallback ----------

_memory_lock = threading.Lock()
_memory_store: Dict[str, Tuple[int, float]] = {}  # key -> (count, expires_at)


def _memory_incr(key: str, window: int) -> Tuple[int, int]:
    now = time.time()
    with _memory_lock:
        # периодическая уборка протухших ключей
        if len(_memory_store) > 10_000:
            for k in [k for k, (_, exp) in _memory_store.items() if exp <= now]:
                _memory_store.pop(k, None)
        count, expires_at = _memory_store.get(key, (0, 0.0))
        if expires_at <= now:
            count, expires_at = 0, now + window
        count += 1
        _memory_store[key] = (count, expires_at)
        return count, max(1, int(expires_at - now))


def _memory_get(key: str) -> int:
    with _memory_lock:
        count, expires_at = _memory_store.get(key, (0, 0.0))
        return count if expires_at > time.time() else 0


def _memory_delete(key: str) -> None:
    with _memory_lock:
        _memory_store.pop(key, None)


def _memory_decr(key: str) -> None:
    with _memory_lock:
        count, expires_at = _memory_store.get(key, (0, 0.0))
        if expires_at > time.time() and count > 0:
            _memory_store[key] = (count - 1, expires_at)


# ---------- redis backend ----------

def _redis():
    from . import ml_service
    return ml_service.get_redis_client()


def _incr(key: str, window: int) -> Tuple[int, int]:
    """Увеличивает счётчик, возвращает (счётчик, секунд до сброса окна)."""
    full_key = _PREFIX + key
    try:
        r = _redis()
        pipe = r.pipeline()
        pipe.incr(full_key)
        pipe.ttl(full_key)
        count, ttl = pipe.execute()
        if ttl is None or int(ttl) < 0:
            r.expire(full_key, window)
            ttl = window
        return int(count), int(ttl)
    except Exception as exc:
        logger.warning("Rate limit: Redis unavailable, using in-memory fallback: %s", exc)
        return _memory_incr(full_key, window)


def _get(key: str) -> int:
    full_key = _PREFIX + key
    try:
        value = _redis().get(full_key)
        return int(value) if value else 0
    except Exception:
        return _memory_get(full_key)


def _delete(key: str) -> None:
    full_key = _PREFIX + key
    try:
        _redis().delete(full_key)
    except Exception:
        pass
    _memory_delete(full_key)


def _decr(key: str) -> None:
    full_key = _PREFIX + key
    try:
        r = _redis()
        if int(r.decr(full_key)) < 0:
            r.delete(full_key)
        return
    except Exception:
        pass
    _memory_decr(full_key)


# ---------- public API ----------

def get_client_ip(request: Request) -> str:
    """IP клиента. За reverse-proxy берём первый адрес из X-Forwarded-For."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def enforce(key: str, limit: int, window: int, detail: str) -> None:
    """Инкремент счётчика; если лимит превышен — 429 с Retry-After."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    count, ttl = _incr(key, window)
    if count > limit:
        logger.warning("Rate limit exceeded", extra={"key": key, "count": count, "limit": limit})
        raise HTTPException(status_code=429, detail=detail, headers={"Retry-After": str(ttl)})


# ---------- брутфорс-защита auth ----------

def check_auth_ip_limit(request: Request) -> None:
    """Общий лимит попыток аутентификации с одного IP (login/token)."""
    ip = get_client_ip(request)
    enforce(
        f"auth:ip:{ip}",
        settings.AUTH_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_RATE_LIMIT_WINDOW,
        "Слишком много попыток входа. Попробуйте позже.",
    )


def check_register_ip_limit(request: Request) -> None:
    """Лимит регистраций с одного IP."""
    ip = get_client_ip(request)
    enforce(
        f"register:ip:{ip}",
        settings.REGISTER_RATE_LIMIT_ATTEMPTS,
        settings.REGISTER_RATE_LIMIT_WINDOW,
        "Слишком много попыток регистрации. Попробуйте позже.",
    )


def _failed_login_key(email: str) -> str:
    return f"auth:fail:{email.strip().lower()}"


def check_failed_login_block(email: str) -> None:
    """До проверки пароля: если по email уже слишком много неудачных попыток — 429.
    Проверка без инкремента, чтобы легитимный вход не блокировал сам себя."""
    if not settings.RATE_LIMIT_ENABLED or not email:
        return
    if _get(_failed_login_key(email)) >= settings.AUTH_FAILED_ATTEMPTS_LIMIT:
        raise HTTPException(
            status_code=429,
            detail="Слишком много неудачных попыток входа. Попробуйте позже.",
            headers={"Retry-After": str(settings.AUTH_FAILED_ATTEMPTS_WINDOW)},
        )


def register_failed_login(email: str) -> None:
    """После неудачной проверки пароля — увеличить счётчик по email."""
    if not settings.RATE_LIMIT_ENABLED or not email:
        return
    _incr(_failed_login_key(email), settings.AUTH_FAILED_ATTEMPTS_WINDOW)


def reset_failed_login(email: str) -> None:
    """Успешный вход сбрасывает счётчик неудач."""
    if not email:
        return
    _delete(_failed_login_key(email))


# ---------- дневной лимит AI-анализа ----------

def _ai_daily_key(user_id: int) -> str:
    return f"ai:daily:{user_id}:{date.today().isoformat()}"


def _seconds_until_midnight() -> int:
    now = datetime.now()
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time())
    return max(1, int((midnight - now).total_seconds()))


def check_ai_daily_limit(user_id: int) -> None:
    """Не более AI_DAILY_LIMIT запросов к анализу фото в сутки на пользователя."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    limit = settings.AI_DAILY_LIMIT
    # Ключ привязан к дате — окно само сбрасывается в полночь; TTL для уборки.
    count, _ = _incr(_ai_daily_key(user_id), 86400 + 3600)
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail=f"Достигнут дневной лимит AI-анализа ({limit} запросов в день). Попробуйте завтра.",
            headers={"Retry-After": str(_seconds_until_midnight())},
        )


def get_ai_daily_usage(user_id: int) -> dict:
    """Текущее использование дневного лимита AI-анализа (для фронтенда)."""
    limit = settings.AI_DAILY_LIMIT
    if not settings.RATE_LIMIT_ENABLED:
        return {"limit": limit, "used": 0, "remaining": limit}
    used = min(_get(_ai_daily_key(user_id)), limit)
    return {"limit": limit, "used": used, "remaining": limit - used}


def refund_ai_daily(user_id: int) -> None:
    """Вернуть попытку, если задача не была поставлена в очередь (ошибка на нашей стороне)."""
    if not settings.RATE_LIMIT_ENABLED:
        return
    _decr(_ai_daily_key(user_id))
