# app/telegram_bot.py

import asyncio
import json
import logging
import os
import secrets as _secrets
import sys

import httpx
import redis
from app.config import settings
from app.api_client import APIClient
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup,
    InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton,
    ReplyKeyboardRemove
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    logger.warning("TELEGRAM_BOT_TOKEN is not set; telegram bot will not start")

API_URL = os.getenv("API_URL", "http://api:8000").rstrip("/")

bot = Bot(token=TOKEN) if TOKEN else None
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# 🔥 хранение токенов
# tokens stored in Redis as hash: tg_tokens:{user_id} -> {access:..., refresh:...}

def _init_redis_client():
    redis_url = getattr(settings, "REDIS_URL", None)
    if not redis_url:
        # Build Redis URL from individual settings
        redis_host = getattr(settings, "REDIS_HOST", "redis")
        redis_port = getattr(settings, "REDIS_PORT", 6379)
        redis_url = f"redis://{redis_host}:{redis_port}/0"

    logger.info(f"Connecting to Redis at {redis_url}")
    try:
        client = redis.from_url(redis_url, decode_responses=True)
        client.ping()
        logger.info("✅ Redis connection successful")
        return client
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        raise


redis_client = _init_redis_client()


def _redis_key(user_id: int) -> str:
    return f"tg_tokens:{user_id}"


def _store_tokens(user_id: int, access: str | None, refresh: str | None = None) -> None:
    key = _redis_key(user_id)
    mapping = {}
    if access is not None:
        mapping["access"] = access
    if refresh is not None:
        mapping["refresh"] = refresh
    if mapping:
        redis_client.hset(key, mapping=mapping)


def _get_tokens(user_id: int) -> tuple[str | None, str | None]:
    key = _redis_key(user_id)
    data = redis_client.hgetall(key) or {}
    return data.get("access"), data.get("refresh")


def _pop_tokens(user_id: int) -> None:
    redis_client.delete(_redis_key(user_id))


api_client = APIClient(API_URL, _get_tokens, _store_tokens, _pop_tokens)


# ==================== ПАРОЛИ TG-АККАУНТОВ ====================
#
# БЕЗОПАСНОСТЬ: раньше паролем был str(user_id). Telegram ID не секрет —
# любой мог залогиниться в аккаунт любого пользователя бота через обычный
# /api/v1/login. Теперь пароль — случайный секрет, который знает только бот
# (хранится в Redis). Старые аккаунты мигрируются на случайный пароль при
# первом обращении (_migrate_legacy_account).

def _password_key(user_id: int) -> str:
    return f"tg_pwd:{user_id}"


def _get_password(user_id: int) -> str | None:
    return redis_client.get(_password_key(user_id))


def _set_password(user_id: int, password: str) -> None:
    redis_client.set(_password_key(user_id), password)


def _email_for(user_id: int) -> str:
    return f"{user_id}@tg.local"


async def _migrate_legacy_account(user_id: int) -> bool:
    """Миграция старого аккаунта (пароль = user_id): логинимся легаси-паролем
    и сразу меняем его на случайный. Возвращает True, если вход выполнен."""
    email = _email_for(user_id)
    legacy_password = str(user_id)

    success, error = await api_client.login(user_id, email, legacy_password)
    if not success:
        logger.error("Legacy login failed", extra={"user_id": user_id, "error": error})
        return False

    new_password = _secrets.token_urlsafe(24)
    changed, change_error = await api_client.change_password(
        user_id, legacy_password, new_password
    )
    if changed:
        _set_password(user_id, new_password)
        logger.info("Legacy account migrated to random password", extra={"user_id": user_id})
    else:
        # Вход выполнен, но пароль сменить не удалось — попробуем при
        # следующем логине. Аккаунт пока остаётся на легаси-пароле.
        logger.warning(
            "Legacy password rotation failed, will retry next login",
            extra={"user_id": user_id, "error": change_error},
        )
    return True


async def register_user(user_id: int) -> bool:
    email = _email_for(user_id)
    password = _get_password(user_id)
    if password is None:
        password = _secrets.token_urlsafe(24)

    success, error = await api_client.register(user_id, email, password)
    if success:
        _set_password(user_id, password)
        logger.info("User registered successfully", extra={"user_id": user_id})
        return True

    if error == "User already exists":
        logger.info("User already exists, continuing", extra={"user_id": user_id})
        return True

    logger.error("Register failed", extra={"user_id": user_id, "error": error})
    return False


async def login_user(user_id: int) -> bool:
    email = _email_for(user_id)

    password = _get_password(user_id)
    if password:
        success, error = await api_client.login(user_id, email, password)
        if success:
            logger.info("User logged in successfully", extra={"user_id": user_id})
            return True
        logger.warning("Stored-password login failed", extra={"user_id": user_id, "error": error})

    # Старый аккаунт с паролем = user_id → мигрируем на случайный пароль
    if await _migrate_legacy_account(user_id):
        return True

    logger.error("Login failed", extra={"user_id": user_id})
    return False


async def register_and_login(user_id: int) -> bool:
    if await login_user(user_id):
        return True
    if not await register_user(user_id):
        return False
    return await login_user(user_id)


async def get_token(user_id: int) -> str | None:
    access, _ = _get_tokens(user_id)
    if access:
        return access

    if await register_and_login(user_id):
        access, _ = _get_tokens(user_id)
        return access
    return None


async def refresh_token(user_id: int) -> str | None:
    success, error = await api_client.refresh_access_token(user_id)
    if success:
        access, _ = _get_tokens(user_id)
        return access

    _pop_tokens(user_id)
    if await register_and_login(user_id):
        access, _ = _get_tokens(user_id)
        return access
    return None


# ===================== FSM =====================

class AuthStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()
    waiting_for_confirm_password = State()
    waiting_for_login_email = State()
    waiting_for_login_password = State()


class FeedbackStates(StatesGroup):
    waiting_for_correct_food = State()
    waiting_for_correct_weight = State()


# ===================== UI =====================

def format_result(result: dict) -> str:
    confidence = result.get('confidence', 0) * 100

    source = result.get("source", "")
    source_text = "⚡ Из кеша\n" if source == "cache" else ""

    ingredients = result.get("ingredients", [])
    if ingredients:
        ingredients_text = "\n".join(
            f"• {i.get('name', '?')} ({i.get('weight_g', 0)} г)"
            for i in ingredients[:5]
        )
        ingredients_block = f"\n🥗 Состав:\n{ingredients_text}\n"
    else:
        ingredients_block = ""

    return (
        f"{source_text}"
        f"🍽️ {result.get('food', '—')}\n\n"
        f"⚖️ Вес: {result.get('weight_g', 0)} г\n"
        f"🔥 Калории: {result.get('calories', 0)} ккал\n\n"
        f"🥩 Белки: {result.get('protein_g', 0)} г\n"
        f"🧈 Жиры: {result.get('fat_g', 0)} г\n"
        f"🍚 Углеводы: {result.get('carbs_g', 0)} г\n"
        f"{ingredients_block}\n"
        f"📊 Уверенность: {confidence:.0f}%"
    )


def get_feedback_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="✅ Верно", callback_data=f"fb_ok_{task_id}"),
            InlineKeyboardButton(text="❌ Неверно", callback_data=f"fb_wrong_{task_id}")
        ]]
    )


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📸 Отправить фото еды")],
            [KeyboardButton(text="🔐 Авторизоваться"), KeyboardButton(text="📝 Зарегистрироваться")],
            [KeyboardButton(text="📊 Статус"), KeyboardButton(text="🚪 Выйти")]
        ],
        resize_keyboard=True
    )


# ===================== HANDLERS =====================

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer(
        "👋 Добро пожаловать в AI Healthy Bot!\n\n"
        "Я помогу проанализировать вашу еду по фото.\n\n"
        "Выберите действие:",
        reply_markup=get_main_menu_keyboard()
    )


@dp.message(F.text == "📊 Статус")
async def status(msg: Message):
    token = await get_token(msg.from_user.id)
    if token:
        await msg.answer("✅ Вы авторизованы", reply_markup=get_main_menu_keyboard())
    else:
        await msg.answer("❌ Вы не авторизованы", reply_markup=get_main_menu_keyboard())


@dp.message(F.text == "📸 Отправить фото еды")
async def send_photo_prompt(msg: Message):
    token = await get_token(msg.from_user.id)
    if not token:
        await msg.answer(
            "❌ Вы не авторизованы. Пожалуйста, авторизуйтесь сначала.",
            reply_markup=get_main_menu_keyboard()
        )
    else:
        await msg.answer(
            "📸 Отправьте фото еды для анализа",
            reply_markup=get_main_menu_keyboard()
        )


@dp.message(F.text == "📝 Зарегистрироваться")
async def register_command(msg: Message, state: FSMContext):
    await state.set_state(AuthStates.waiting_for_email)
    await msg.answer(
        "📧 Введите ваш email:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(F.text == "🔐 Авторизоваться")
async def login_command(msg: Message, state: FSMContext):
    await state.set_state(AuthStates.waiting_for_login_email)
    await msg.answer(
        "📧 Введите ваш email:",
        reply_markup=get_cancel_keyboard()
    )


# ===================== AUTH HANDLERS =====================

@dp.message(AuthStates.waiting_for_email)
async def process_register_email(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена", reply_markup=get_main_menu_keyboard())
        return

    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("❌ Неверный формат email. Попробуйте снова:")
        return

    await state.update_data(email=email)
    await state.set_state(AuthStates.waiting_for_password)
    await message.answer(
        "🔒 Введите пароль (минимум 8 символов):",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(AuthStates.waiting_for_password)
async def process_register_password(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена", reply_markup=get_main_menu_keyboard())
        return

    password = message.text.strip()
    if len(password) < 8:
        await message.answer("❌ Пароль должен быть минимум 8 символов. Попробуйте снова:")
        return

    await state.update_data(password=password)
    await state.set_state(AuthStates.waiting_for_confirm_password)
    await message.answer(
        "🔒 Подтвердите пароль:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(AuthStates.waiting_for_confirm_password)
async def process_register_confirm(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Регистрация отменена", reply_markup=get_main_menu_keyboard())
        return

    data = await state.get_data()
    password = data.get("password")
    confirm = message.text.strip()

    if password != confirm:
        await message.answer("❌ Пароли не совпадают. Попробуйте снова:")
        return

    if await api_client.register(message.from_user.id, data["email"], password):
        await message.answer("✅ Регистрация успешна! Теперь авторизуйтесь.", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("❌ Не удалось зарегистрироваться. Попробуйте позже.",
                             reply_markup=get_main_menu_keyboard())

    await state.clear()


@dp.message(AuthStates.waiting_for_login_email)
async def process_login_email(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Авторизация отменена", reply_markup=get_main_menu_keyboard())
        return

    email = message.text.strip()
    if "@" not in email or "." not in email:
        await message.answer("❌ Неверный формат email. Попробуйте снова:")
        return

    await state.update_data(email=email)
    await state.set_state(AuthStates.waiting_for_login_password)
    await message.answer(
        "🔒 Введите пароль:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(AuthStates.waiting_for_login_password)
async def process_login_password(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Авторизация отменена", reply_markup=get_main_menu_keyboard())
        return

    data = await state.get_data()
    email = data.get("email")
    password = message.text.strip()

    if await api_client.login(message.from_user.id, email, password):
        await message.answer("✅ Авторизация успешна!", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("❌ Неверный email или пароль или ошибка соединения", reply_markup=get_main_menu_keyboard())

    await state.clear()


@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    token = await get_token(message.from_user.id)
    if not token:
        await message.answer(
            "❌ Вы не авторизованы. Пожалуйста, авторизуйтесь сначала.",
            reply_markup=get_main_menu_keyboard()
        )
        return

    msg = await message.answer("🔍 Загружаю фото и запускаю анализ...")

    try:
        photo = message.photo[-1]
        file_info = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file_info.file_path)

        task, error = await api_client.upload_photo(
            message.from_user.id,
            file_bytes,
            filename="image.jpg"
        )

        if error or not task:
            await msg.edit_text(f"❌ Ошибка при отправке изображения: {error or 'unknown'}")
            return

        task_id = task.get("id")
        if not task_id:
            await msg.edit_text("❌ Сервер не вернул ID задачи")
            return

        await msg.edit_text("⌛ Задача зарегистрирована, ожидаю результат...")

        # ========== УЛУЧШЕННОЕ ОЖИДАНИЕ РЕЗУЛЬТАТА ==========
        MAX_WAIT_SECONDS = 60
        start_time = asyncio.get_event_loop().time()
        attempt = 0
        result = None

        while (asyncio.get_event_loop().time() - start_time) < MAX_WAIT_SECONDS:
            attempt += 1
            data, error = await api_client.get_task_status(message.from_user.id, task_id)

            if error:
                logger.warning(f"Task status error (attempt {attempt}): {error}")
                await asyncio.sleep(min(1.0 * (1.2 ** attempt), 5.0))
                continue

            if not data:
                await asyncio.sleep(min(1.0 * (1.2 ** attempt), 5.0))
                continue

            # Логируем ответ для диагностики
            logger.info(f"Task status response (attempt {attempt}): {data}")

            status = str(data.get("status", "")).lower()

            # Признаки успешного завершения
            success_statuses = {"success", "completed", "done"}

            if status in success_statuses:
                # Пытаемся извлечь результат из разных полей
                result = (
                        data.get("result") or
                        data.get("result_json") or
                        data.get("output") or
                        data.get("data")
                )
                if result:
                    # Если результат – строка JSON, парсим
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse result JSON, keeping as string")
                    break
                else:
                    # Статус успешный, но результат отсутствует – возможно, ещё не записался
                    logger.warning(f"Status {status} but no result found in data: {data}")
                    # Дадим ещё несколько попыток
                    await asyncio.sleep(1.0)
                    continue

            elif status in ("pending", "processing", "started"):
                if attempt % 5 == 0:
                    elapsed = int(asyncio.get_event_loop().time() - start_time)
                    await msg.edit_text(f"⌛ Анализ продолжается... (прошло {elapsed} сек)")
                await asyncio.sleep(min(1.0 * (1.2 ** attempt), 5.0))
                continue

            elif status == "failure":
                error_msg = data.get("error", "Неизвестная ошибка")
                await msg.edit_text(f"❌ Ошибка анализа: {error_msg}")
                return

            else:
                # Неизвестный статус – пробуем извлечь результат на всякий случай
                logger.warning(f"Unknown status: {status}, trying to extract result")
                result = (
                        data.get("result") or
                        data.get("result_json") or
                        data.get("output") or
                        data.get("data")
                )
                if result:
                    if isinstance(result, str):
                        try:
                            result = json.loads(result)
                        except json.JSONDecodeError:
                            pass
                    break
                else:
                    await asyncio.sleep(min(1.0 * (1.2 ** attempt), 5.0))
                    continue

        # Если результат так и не получен, делаем последнюю попытку
        if not result:
            data, error = await api_client.get_task_status(message.from_user.id, task_id)
            if data:
                result = (
                        data.get("result") or
                        data.get("result_json") or
                        data.get("output") or
                        data.get("data")
                )
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        pass

        if result:
            await msg.edit_text(
                format_result(result),
                reply_markup=get_feedback_keyboard(task_id)
            )
        else:
            await msg.edit_text("❌ Не удалось получить результат за отведённое время. Попробуйте ещё раз.")

    except Exception as exc:
        logger.exception("Error handling photo", exc_info=exc)
        await msg.edit_text("❌ Ошибка при обработке изображения. Попробуйте позже.")


# ===================== FEEDBACK =====================

@dp.callback_query(F.data.startswith("fb_ok_"))
async def feedback_ok(callback: CallbackQuery):
    await callback.answer("Спасибо! 🙏")
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("Спасибо за обратную связь!", reply_markup=get_main_menu_keyboard())


@dp.callback_query(F.data.startswith("fb_wrong_"))
async def feedback_wrong(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.split("_")[2]

    await state.update_data(task_id=task_id)
    await state.set_state(FeedbackStates.waiting_for_correct_food)

    await callback.message.answer(
        "🍽 Напиши правильное название блюда:",
        reply_markup=get_cancel_keyboard()
    )

    await callback.answer()


@dp.message(FeedbackStates.waiting_for_correct_food)
async def process_correct_food(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_menu_keyboard())
        return

    await state.update_data(correct_food=message.text.strip())
    await state.set_state(FeedbackStates.waiting_for_correct_weight)

    await message.answer(
        "⚖️ Укажи вес:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(FeedbackStates.waiting_for_correct_weight)
async def process_correct_weight(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено", reply_markup=get_main_menu_keyboard())
        return

    try:
        weight = int(message.text)
    except:
        await message.answer("Введите число")
        return

    data = await state.get_data()

    payload = {
        "task_id": data["task_id"],
        "correct_food": data["correct_food"],
        "correct_weight": weight
    }

    success, error = await api_client.submit_feedback(
        message.from_user.id,
        data["task_id"],
        data["correct_food"],
        weight,
    )

    if success:
        await message.answer("✅ Сохранено", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer(f"⚠️ Ошибка сохранения: {error or 'Неизвестная ошибка'}",
                             reply_markup=get_main_menu_keyboard())

    await state.clear()


# ===================== START =====================

async def wait_for_api(max_attempts: int = 30, delay: int = 2) -> bool:
    """Wait for API to be ready before starting the bot"""
    logger.info(f"🔄 Waiting for API at {API_URL}...")
    for attempt in range(max_attempts):
        try:
            # Try to access any endpoint to check if API is ready
            response = await api_client.client.get("/health", timeout=5)
            if response.status_code == 200:
                logger.info("✅ API is ready!")
                return True
        except httpx.ConnectError as e:
            logger.warning(f"❌ Cannot connect to API (attempt {attempt + 1}/{max_attempts}): Connection refused - {e}")
        except httpx.TimeoutException as e:
            logger.warning(f"⏱️ API timeout (attempt {attempt + 1}/{max_attempts}): {e}")
        except Exception as e:
            logger.warning(f"❌ API check failed (attempt {attempt + 1}/{max_attempts}): {type(e).__name__} - {e}")

        if attempt < max_attempts - 1:
            logger.info(f"   Retrying in {delay}s...")
            await asyncio.sleep(delay)

    logger.error(f"❌ API failed to become ready after {max_attempts} attempts")
    return False


async def main():
    if not TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN is not set! Cannot start bot.")
        return

    if not await wait_for_api():
        logger.error("❌ Failed to connect to API. Exiting.")
        return

    logger.info("Starting Telegram bot")
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        logger.exception("Telegram bot error", exc_info=e)


if __name__ == "__main__":
    asyncio.run(main())