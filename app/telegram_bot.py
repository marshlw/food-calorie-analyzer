# app/telegram_bot.py
import asyncio
import logging
import os
import sys
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

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


# ===================== FSM =====================

class FeedbackStates(StatesGroup):
    waiting_for_correct_food = State()
    waiting_for_correct_weight = State()


# ===================== UI =====================

def format_result(result: dict) -> str:
    confidence = result.get('confidence', 0) * 100

    # 🔥 источник
    source = result.get("source", "")
    source_text = "⚡ Из кеша\n" if source == "cache" else ""

    # 🔥 ингредиенты
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


# ===================== HANDLERS =====================

@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("📸 Отправь фото еды — я посчитаю КБЖУ")


@dp.message(F.photo)
async def handle_photo(message: Message, state: FSMContext):
    msg = await message.answer("🔍 Анализирую...")

    try:
        photo = message.photo[-1]

        # 🔥 получаем файл как bytes (без сохранения на диск)
        file = await bot.get_file(photo.file_id)
        file_bytes = await bot.download_file(file.file_path)

        # 🔥 RETRY LOGIC
        max_retries = 3
        retry_delay = 1
        result = None

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    form = aiohttp.FormData()
                    form.add_field("file", file_bytes, filename="image.jpg")

                    # 🔹 отправка в API с timeout
                    try:
                        async with session.post(
                            f"{API_URL}/api/v1/analyze",
                            data=form,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as resp:
                            if resp.status != 200:
                                logger.error(f"Analyze API error: {resp.status}")
                                if attempt < max_retries - 1:
                                    await asyncio.sleep(retry_delay)
                                    retry_delay *= 2
                                    continue
                                else:
                                    await msg.edit_text("❌ Ошибка при отправке на анализ")
                                    return

                            task = await resp.json()

                        task_id = task["id"]

                        # 🔹 polling с адаптивной задержкой
                        result = None
                        delay = 1

                        for poll_attempt in range(40):  # увеличили до 40 попыток
                            await asyncio.sleep(delay)
                            delay = min(delay * 1.2, 5)

                            async with session.get(
                                f"{API_URL}/api/v1/task/{task_id}",
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as resp:
                                if resp.status != 200:
                                    logger.warning(f"Task status check failed: {resp.status}")
                                    continue

                                data = await resp.json()

                                if data["status"] == "success":
                                    result = data["result"]
                                    break

                                elif data["status"] in ["failure", "error"]:
                                    logger.error(f"Task failed: {data.get('error', 'unknown')}")
                                    break

                        if result:
                            break  # успешно получили результат
                        else:
                            if attempt < max_retries - 1:
                                logger.info(f"Retrying analysis (attempt {attempt + 2}/{max_retries})")
                                await asyncio.sleep(retry_delay)
                                retry_delay *= 2
                            else:
                                await msg.edit_text("❌ Не удалось обработать изображение")
                                return

                    except asyncio.TimeoutError:
                        logger.warning(f"Request timeout (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            await msg.edit_text("❌ Время ожидания истекло")
                            return
                    except Exception as e:
                        logger.warning(f"Request error: {e} (attempt {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            retry_delay *= 2
                        else:
                            await msg.edit_text("❌ Ошибка соединения с сервером")
                            return

            except Exception as e:
                logger.exception(f"Session error: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                else:
                    await msg.edit_text("❌ Ошибка при обработке")
                    return

        if result:
            await msg.edit_text(
                format_result(result),
                reply_markup=get_feedback_keyboard(task_id)
            )

    except Exception as e:
        logger.exception("Error handling photo")
        await msg.edit_text("❌ Ошибка при обработке")


# ===================== FEEDBACK =====================

@dp.callback_query(F.data.startswith("fb_ok_"))
async def feedback_ok(callback: CallbackQuery):
    await callback.answer("Спасибо за подтверждение! 🙏")
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
        await message.answer("Название не может быть пустым. Попробуй ещё раз:")
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
        await message.answer("Введи число от 1 до 10000")
        return

    data = await state.get_data()
    task_id = data["task_id"]
    correct_food = data["correct_food"]

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
                    await message.answer(
                        "🙏 Спасибо! Я учту это в будущем.",
                        reply_markup=ReplyKeyboardRemove()
                    )
                else:
                    logger.warning(f"Feedback API error: {resp.status}")
                    await message.answer(
                        "⚠️ Не удалось сохранить, но спасибо!",
                        reply_markup=ReplyKeyboardRemove()
                    )

    except Exception:
        logger.exception("Feedback error")
        await message.answer(
            "⚠️ Ошибка соединения с сервером",
            reply_markup=ReplyKeyboardRemove()
        )

    await state.clear()


# ===================== START =====================

async def main():
    logger.info("Starting Telegram bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())