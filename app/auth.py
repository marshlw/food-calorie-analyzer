import uuid
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .config import settings
from . import crud
from .database import get_db
from . import models
import logging

logger = logging.getLogger(__name__)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/token")

def _truncate_password(password: str) -> bytes:
    """Обрезает пароль до 72 байт (ограничение bcrypt)"""
    return password.encode('utf-8')[:72]

def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = _truncate_password(plain_password)
    try:
        return bcrypt.checkpw(truncated, hashed_password.encode('utf-8'))
    except ValueError:
        return False

def get_password_hash(password: str) -> str:
    truncated = _truncate_password(password)
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode('utf-8')

def token_claims_for(user: models.User) -> dict:
    """Стандартные claims для access/refresh токенов пользователя.
    "tv" (token version) позволяет мгновенно отозвать все токены,
    инкрементировав users.token_version (например, при смене пароля)."""
    return {"sub": user.email, "tv": user.token_version or 0}


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Создаёт refresh-токен и РЕГИСТРИРУЕТ его jti как активный.

    jti нужен для одноразового использования: при обмене токен гасится
    (consume_refresh_jti), и повторное предъявление того же jti трактуется
    как компрометация — обработка в эндпоинте POST /api/v1/token.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    jti = uuid.uuid4().hex
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti})

    _register_refresh_jti(data.get("sub"), jti, expire)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ===================== РОТАЦИЯ REFRESH-ТОКЕНОВ =====================

def _refresh_key(subject: str, jti: str) -> str:
    return f"refresh:{subject}:{jti}"


def _refresh_store():
    """Redis для учёта активных refresh-токенов.

    Если Redis недоступен, возвращаем None: ротация деградирует до
    прежнего поведения (токен просто живёт до exp). Это осознанный
    компромисс — иначе падение Redis разлогинило бы всех.
    """
    try:
        from .ml_service import get_redis_client
        return get_redis_client()
    except Exception as exc:
        logger.warning("Refresh token store unavailable", exc_info=exc)
        return None


# Сторож целостности хранилища. Живёт дольше любого refresh-токена и
# обновляется при каждой выдаче. Если сторожа нет, а jti не найден — значит
# Redis потерял данные (переезд, FLUSHALL, потеря AOF), а не кто-то предъявил
# краденый токен. Без этой проверки любая чистка Redis разлогинивала бы всех
# пользователей с формулировкой «обнаружена компрометация».
# Префикс намеренно отличается от "refresh:", чтобы сторож не попал под
# маску refresh:{subject}:* в revoke_all_refresh_tokens.
_ALIVE_KEY = "refresh_store:alive"


def _store_alive_ttl() -> int:
    return settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400 + 86400


def _register_refresh_jti(subject: Optional[str], jti: str, expire: datetime) -> None:
    if not subject:
        return
    store = _refresh_store()
    if store is None:
        return
    ttl = max(1, int((expire - datetime.utcnow()).total_seconds()))
    try:
        pipe = store.pipeline()
        pipe.setex(_refresh_key(subject, jti), ttl, "1")
        pipe.setex(_ALIVE_KEY, _store_alive_ttl(), "1")
        pipe.execute()
    except Exception as exc:
        logger.warning("Unable to register refresh token", exc_info=exc)


# Окно, в течение которого повторное предъявление только что погашенного
# токена НЕ считается кражей. Нужно из-за гонки вкладок: две вкладки читают
# один refresh из localStorage и обновляются почти одновременно. Внутри
# одной вкладки гонку снимает tokenRefreshPromise (frontend/src/api/axios.ts),
# между вкладками — только это окно.
REFRESH_GRACE_SECONDS = 20


def _grace_key(subject: str, jti: str) -> str:
    return f"refresh:used:{subject}:{jti}"


def consume_refresh_jti(subject: str, jti: Optional[str]) -> bool:
    """Гасит jti. True — токен можно обменять.

    False означает, что токен предъявлен повторно уже ПОСЛЕ grace-окна:
    легитимный клиент так себя не ведёт, значит копия токена у кого-то ещё.
    """
    if not jti:
        return False
    store = _refresh_store()
    if store is None:
        # Redis лежит — не блокируем вход, работаем как раньше (H-2 деградирует)
        return True

    try:
        if store.delete(_refresh_key(subject, jti)):
            # Токен был активен. Оставляем короткую метку «только что
            # использован», чтобы соседняя вкладка не словила ложную тревогу.
            store.setex(_grace_key(subject, jti), REFRESH_GRACE_SECONDS, "1")
            return True

        # Активного ключа нет. Проверяем grace-окно.
        if store.get(_grace_key(subject, jti)):
            logger.info("Refresh token reused within grace window", extra={"jti": jti})
            return True

        # Ключа нет и сторожа нет — хранилище потеряло данные, а не кража.
        # Пропускаем один раз; выданный в ответ токен уже будет учтён.
        if not store.get(_ALIVE_KEY):
            logger.warning(
                "Refresh store looks empty, skipping reuse detection",
                extra={"jti": jti},
            )
            return True

        return False
    except Exception as exc:
        logger.warning("Unable to consume refresh token", exc_info=exc)
        return True


def revoke_all_refresh_tokens(subject: str) -> None:
    """Гасит все активные refresh-токены пользователя.

    Вызывается при обнаружении повторного использования. Точечно удалить
    ключи по маске нельзя без SCAN, поэтому основную работу делает
    инкремент users.token_version — он инвалидирует и access, и refresh.
    Здесь подчищаем то, что найдём, чтобы не копить мусор в Redis.
    """
    store = _refresh_store()
    if store is None:
        return
    try:
        pattern = _refresh_key(subject, "*")
        # SCAN, а не KEYS: не блокируем Redis (ключей может быть много)
        for key in store.scan_iter(match=pattern, count=100):
            store.delete(key)
    except Exception as exc:
        logger.warning("Unable to revoke refresh tokens", exc_info=exc)


def _decode_token(token: str, token_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != token_type:
            raise JWTError("Invalid token type")
        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def authenticate_user_sync(db: Session, email: str, password: str) -> Optional[models.User]:
    """Синхронная версия для authenticate_user"""
    user = crud.get_user_by_email_sync(db, email)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    payload = _decode_token(token, "access")
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = crud.get_user_by_email_sync(db, email)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Токены, выданные до смены пароля (bump token_version), недействительны.
    # Старые токены без "tv" трактуем как tv=0 — обратная совместимость.
    if int(payload.get("tv") or 0) != int(user.token_version or 0):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def verify_refresh_token(token: str) -> dict:
    """Проверяет refresh-токен, возвращает payload (sub, tv, ...).
    Сверку tv с БД делает вызывающий код (нужен пользователь из БД)."""
    payload = _decode_token(token, "refresh")
    if not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload