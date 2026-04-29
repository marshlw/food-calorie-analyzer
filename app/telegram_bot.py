# app/telegram_bot.py

import asyncio
import logging
import os
import sys

import aiohttp
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
    logger.error("TELEGRAM_BOT_TOKEN is not set")
    sys.exit(1)

API_URL = os.getenv("API_URL", "http://api:8000").rstrip("/")

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# 🔥 хранение токенов
user_tokens: dict[int, str] = {}

# ===================== AUTH =====================

async def register_user(user_id: int) -> bool:
    email = f"{user_id}@tg.local"
    password = str(user_id)

    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{API_URL}/api/v1/register",
                json={"email": email, "password": password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"User {user_id} registered successfully")
                    return True
                elif resp.status == 400:
                    logger.info(f"User {user_id} already exists")
                    return True
                else:
                    logger.error(f"Register failed for {user_id}: {resp.status}")
                    return False
        except Exception as e:
            logger.error(f"Register error for {user_id}: {e}")
            return False


async def login_user(user_id: int) -> str | None:
    email = f"{user_id}@tg.local"
    password = str(user_id)

    async with aiohttp.ClientSession() as session:
        try:
            form = aiohttp.FormData()
            form.add_field("email", email)
            form.add_field("password", password)

            async with session.post(
                f"{API_URL}/api/v1/login",
                data=form,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("access_token")
                    if token:
                        logger.info(f"User {user_id} logged in successfully")
                        return token
                    else:
                        logger.error(f"Login response missing token for {user_id}")
                        return None
                else:
                    logger.error(f"Login failed for {user_id}: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"Login error for {user_id}: {e}")
            return None


async def register_and_login(user_id: int) -> str | None:
    # Сначала пытаемся зарегистрировать (если не существует)
    await register_user(user_id)
    # Затем логинимся
    return await login_user(user_id)


async def get_token(user_id: int) -> str | None:
    if user_id in user_tokens:
        return user_tokens[user_id]

    token = await register_and_login(user_id)
    if token:
        user_tokens[user_id] = token

    return token


async def refresh_token(user_id: int) -> str | None:
    """Обновляет токен для пользователя"""
    user_tokens.pop(user_id, None)
    return await get_token(user_id)


async def make_authenticated_request(method: str, url: str, user_id: int, **kwargs) -> aiohttp.ClientResponse | None:
    """Делает запрос с авторизацией, автоматически обновляя токен при 401"""
    token = await get_token(user_id)
    if not token:
        return None

    headers = kwargs.get('headers', {})
    headers['Authorization'] = f"Bearer {token}"
    kwargs['headers'] = headers
    kwargs.setdefault('timeout', aiohttp.ClientTimeout(total=30))

    async with aiohttp.ClientSession() as session:
        for attempt in range(2):  # Одна попытка с текущим токеном, вторая с новым
            try:
                async with session.request(method, url, **kwargs) as resp:
                    if resp.status == 401 and attempt == 0:
                        # Токен истек, обновляем и повторяем
                        logger.warning(f"Token expired for user {user_id}, refreshing")
                        token = await refresh_token(user_id)
                        if token:
                            headers['Authorization'] = f"Bearer {token}"
                            continue
                        else:
                            return None
                    return resp
            except Exception as e:
                logger.error(f"Request error: {e}")
                return None
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


@dp.message(F.text == "� Отправить фото еды")
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

    # Регистрация
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                f"{API_URL}/api/v1/register",
                json={"email": data["email"], "password": password},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    await message.answer("✅ Регистрация успешна! Теперь авторизуйтесь.", reply_markup=get_main_menu_keyboard())
                elif resp.status == 400:
                    await message.answer("❌ Пользователь уже существует", reply_markup=get_main_menu_keyboard())
                else:
                    await message.answer("❌ Ошибка регистрации", reply_markup=get_main_menu_keyboard())
        except Exception as e:
            logger.error(f"Register error: {e}")
            await message.answer("❌ Ошибка соединения", reply_markup=get_main_menu_keyboard())

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

    # Логин
    async with aiohttp.ClientSession() as session:
        try:
            form = aiohttp.FormData()
            form.add_field("email", email)
            form.add_field("password", password)

            async with session.post(
                f"{API_URL}/api/v1/login",
                data=form,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    login_data = await resp.json()
                    token = login_data.get("access_token")
                    if token:
                        user_tokens[message.from_user.id] = token
                        await message.answer("✅ Авторизация успешна!", reply_markup=get_main_menu_keyboard())
                    else:
                        await message.answer("❌ Ошибка получения токена", reply_markup=get_main_menu_keyboard())
                else:
                    await message.answer("❌ Неверный email или пароль", reply_markup=get_main_menu_keyboard())
        except Exception as e:
            logger.error(f"Login error: {e}")
            await message.answer("❌ Ошибка соединения", reply_markup=get_main_menu_keyboard())

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

    msg = await message.answer("🔍 Анализирую...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        # Отправляем файл на анализ
        form = aiohttp.FormData()
        form.add_field("file", file_bytes, filename="image.jpg")

        resp = await make_authenticated_request(
            "POST",
            f"{API_URL}/api/v1/analyze",
            message.from_user.id,
            data=form
        )

        if not resp or resp.status != 200:
            await msg.edit_text("❌ Ошибка при отправке изображения")
            return

        task = await resp.json()
        task_id = task["id"]

        # Ждем результат
        result = None
        delay = 1

        for _ in range(40):  # Максимум 40 попыток
            await asyncio.sleep(delay)
            delay = min(delay * 1.2, 5)

            resp = await make_authenticated_request(
                "GET",
                f"{API_URL}/api/v1/task/{task_id}",
                message.from_user.id
            )

            if not resp or resp.status != 200:
                continue

            data = await resp.json()

            if data["status"] == "success":
                result = data["result"]
                break
            elif data["status"] == "failure":
                await msg.edit_text(f"❌ Ошибка анализа: {data.get('error', 'Неизвестная ошибка')}")
                return

        if result:
            await msg.edit_text(
                format_result(result),
                reply_markup=get_feedback_keyboard(task_id)
            )
        else:
            await msg.edit_text("❌ Не удалось обработать изображение (таймаут)")

    except Exception:
        logger.exception("Error handling photo")
        await msg.edit_text("❌ Ошибка при обработке")


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

    resp = await make_authenticated_request(
        "POST",
        f"{API_URL}/api/v1/feedback",
        message.from_user.id,
        json=payload
    )

    if resp and resp.status == 200:
        await message.answer("✅ Сохранено", reply_markup=get_main_menu_keyboard())
    else:
        await message.answer("⚠️ Ошибка сохранения", reply_markup=get_main_menu_keyboard())

    await state.clear()


# ===================== START =====================

async def main():
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())