# app/telegram_bot.py
import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

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

# Папка для сохранения загруженных фото (должна совпадать с UPLOAD_DIR в API)
UPLOAD_DIR = Path("/app/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class FeedbackStates(StatesGroup):
    waiting_for_correct_food = State()
    waiting_for_correct_weight = State()


def format_result(result: dict) -> str:
    """Форматирует результат анализа для отправки пользователю."""
    confidence = result.get('confidence', 0) * 100
    return (
        f"🍽️ {result['food']}\n\n"
        f"⚖️ Вес: {result['weight_g']} г\n"
        f"🔥 Калории: {result['calories']} ккал\n\n"
        f"🥩 Белки: {result['protein_g']} г\n"
        f"🧈 Жиры: {result['fat_g']} г\n"
        f"🍚 Углеводы: {result['carbs_g']} г\n\n"
        f"📊 Уверенность: {confidence:.0f}%"
    )


def get_feedback_keyboard(task_id: str) -> InlineKeyboardMarkup:
    """Клавиатура с кнопками «Верно» / «Неверно»."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Верно", callback_data=f"fb_ok_{task_id}"),
            InlineKeyboardButton(text="❌ Неверно", callback_data=f"fb_wrong_{task_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены для состояний FSM."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("📸 Отправь фото еды — я посчитаю КБЖУ")


@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    msg = await message.answer("🔍 Анализирую...")

    try:
        # Скачиваем фото
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)
        file_path = UPLOAD_DIR / f"{uuid4()}.jpg"
        await bot.download_file(file.file_path, destination=file_path)

        # Отправляем на анализ
        async with aiohttp.ClientSession() as session:
            with open(file_path, "rb") as img:
                form = aiohttp.FormData()
                form.add_field("file", img, filename="img.jpg")
                async with session.post(f"{API_URL}/api/v1/analyze", data=form) as resp:
                    if resp.status != 200:
                        await msg.edit_text("❌ Ошибка при отправке на анализ")
                        return
                    task = await resp.json()

            task_id = task["id"]

            # Опрос статуса задачи
            result = None
            delay = 1
            for _ in range(20):
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 5)
                async with session.get(f"{API_URL}/api/v1/task/{task_id}") as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.json()
                    if data["status"] == "success":
                        result = data["result"]
                        break
                    elif data["status"] == "failure":
                        break

            if not result:
                await msg.edit_text("❌ Не удалось обработать изображение")
                return

            await msg.edit_text(
                format_result(result),
                reply_markup=get_feedback_keyboard(task_id)
            )

    except Exception as e:
        logger.exception("Error handling photo")
        await msg.edit_text("❌ Ошибка при обработке")


# ---------- Обработчики обратной связи ----------
@dp.callback_query(F.data.startswith("fb_ok_"))
async def feedback_ok(callback: CallbackQuery):
    await callback.answer("Спасибо за подтверждение!")
    await callback.message.edit_reply_markup(reply_markup=None)


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
        await message.answer("Исправление отменено", reply_markup=ReplyKeyboardRemove())
        return

    food = message.text.strip()
    if not food:
        await message.answer("Название не может быть пустым. Попробуйте ещё раз:")
        return

    await state.update_data(correct_food=food)
    await state.set_state(FeedbackStates.waiting_for_correct_weight)
    await message.answer(
        "⚖️ Укажи примерный вес в граммах:",
        reply_markup=get_cancel_keyboard()
    )


@dp.message(FeedbackStates.waiting_for_correct_weight)
async def process_correct_weight(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Исправление отменено", reply_markup=ReplyKeyboardRemove())
        return

    try:
        weight = int(message.text.strip())
        if weight <= 0 or weight > 10000:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введи целое положительное число (до 10000 г).")
        return

    data = await state.get_data()
    task_id = data["task_id"]
    correct_food = data["correct_food"]

    # Отправляем исправление на API
    success = False
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "task_id": task_id,
                "correct_food": correct_food,
                "correct_weight": weight,
                "user_id": message.from_user.id
            }
            async with session.post(f"{API_URL}/api/v1/feedback", json=payload) as resp:
                if resp.status == 200:
                    success = True
                    await message.answer(
                        "🙏 Спасибо! Я учту это в будущем.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    error_text = await resp.text()
                    logger.warning(f"Feedback API returned {resp.status}: {error_text}")
                    await message.answer(
                        "⚠️ Не удалось сохранить исправление, но спасибо за участие!",
                        reply_markup=ReplyKeyboardRemove()
                    )
    except Exception as e:
        logger.exception("Failed to send feedback")
        await message.answer(
            "⚠️ Ошибка соединения с сервером. Исправление не сохранено.",
            reply_markup=ReplyKeyboardRemove()
        )

    await state.clear()


async def main():
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())