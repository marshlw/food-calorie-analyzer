import asyncio
import logging
import os
import sys
import json
import uuid
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

from aiogram import Bot, Dispatcher, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp
from PIL import Image

# --- Логирование ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Конфигурация ---
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")  # для Docker; для локального теста: "http://localhost:8000"

# Директории для сбора обучающих данных
TRAIN_DIR = Path("app/training_data")
IMAGES_DIR = TRAIN_DIR / "images"
ANNOTATIONS_FILE = TRAIN_DIR / "annotations.jsonl"
TEMP_DIR = Path("temp_images")  # для временного хранения фото перед отправкой в API

# Создаём папки
TRAIN_DIR.mkdir(exist_ok=True)
IMAGES_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


# --- Состояния FSM ---
class FeedbackState(StatesGroup):
    waiting_for_correction = State()


# --- Инициализация бота и диспетчера ---
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)


# --- Функция сохранения обучающего примера ---
def save_training_sample(image_path: str, correct_label: str, original_result: Dict[str, Any] = None,
                         is_correct: bool = False) -> None:
    """
    Сохраняет изображение и аннотацию в training_data/
    """
    # Генерируем уникальное имя для изображения
    unique_name = f"{uuid.uuid4()}.jpg"
    dest_path = IMAGES_DIR / unique_name

    # Копируем изображение (можно предварительно сжать)
    try:
        # Открываем и конвертируем в RGB, сжимаем
        img = Image.open(image_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(dest_path, 'JPEG', quality=85)
        logger.info(f"Saved image: {dest_path}")
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        return

    # Формируем аннотацию
    annotation = {
        "image": str(dest_path),
        "food": correct_label,
        "original_food": original_result.get("food") if original_result else None,
        "is_correct": is_correct,
        "timestamp": datetime.utcnow().isoformat(),
        "confidence_original": original_result.get("confidence") if original_result else None
    }

    # Дописываем в JSONL файл
    with open(ANNOTATIONS_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(annotation, ensure_ascii=False) + "\n")

    logger.info(f"Saved annotation for {correct_label}")


# --- Обработчики команд ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🍽️ Привет! Я бот для анализа калорийности блюд по фотографии.\n\n"
        "Просто отправь мне фото еды, и я постараюсь определить:\n"
        "🍲 Название блюда\n⚖️ Вес порции\n🔥 КБЖУ\n\n"
        "После результата ты сможешь подтвердить или исправить название блюда — это поможет улучшить распознавание!"
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "ℹ️ Справка:\n\n"
        "1. Отправьте фото блюда.\n"
        "2. Дождитесь результата анализа.\n"
        "3. Нажмите ✅ 'Верно' или ✏️ 'Исправить'.\n"
        "4. Если исправляете, напишите правильное название блюда.\n\n"
        "Спасибо за помощь в обучении модели!"
    )


# --- Основной обработчик фото ---
@dp.message(lambda message: message.photo)
async def handle_photo(message: Message, state: FSMContext):
    # Отправляем сообщение "обрабатывается"
    processing_msg = await message.answer("🔄 Анализирую фотографию... Это может занять до 30 секунд.")

    # Скачиваем фото (самое большое разрешение)
    photo = message.photo[-1]
    file_info = await bot.get_file(photo.file_id)
    file_bytes = await bot.download_file(file_info.file_path)

    # Сохраняем временную копию локально (для отправки в API и для возможного сохранения в обучение)
    temp_image_path = TEMP_DIR / f"{photo.file_id}.jpg"
    with open(temp_image_path, "wb") as f:
        f.write(file_bytes.read())

    # --- Взаимодействие с FastAPI ---
    async with aiohttp.ClientSession() as session:
        # 1. Регистрация / получение токена (используем chat_id как email)
        chat_id = message.chat.id
        fake_email = f"tg_user_{chat_id}@telegram.bot"
        fake_password = "tg_bot_password_123"

        # Регистрация (если пользователь уже есть, API вернёт ошибку, но мы её игнорируем)
        try:
            await session.post(f"{API_URL}/api/v1/register", json={
                "email": fake_email,
                "password": fake_password,
                "full_name": f"Telegram User {chat_id}"
            })
        except:
            pass

        # Получение токена
        token_data = {"username": fake_email, "password": fake_password}
        async with session.post(f"{API_URL}/api/v1/token", data=token_data) as token_resp:
            if token_resp.status != 200:
                await processing_msg.edit_text("❌ Не удалось авторизоваться на сервере. Попробуйте позже.")
                return
            token_json = await token_resp.json()
            access_token = token_json["access_token"]
            headers = {"Authorization": f"Bearer {access_token}"}

        # Отправляем фото на анализ (используя временный файл)
        with open(temp_image_path, "rb") as img_file:
            form_data = aiohttp.FormData()
            form_data.add_field('file', img_file, filename='photo.jpg', content_type='image/jpeg')
            async with session.post(f"{API_URL}/api/v1/analyze", headers=headers, data=form_data) as analyze_resp:
                if analyze_resp.status != 200:
                    await processing_msg.edit_text("❌ Ошибка при отправке фото на сервер. Попробуйте ещё раз.")
                    return
                task_json = await analyze_resp.json()
                task_id = task_json["id"]

        # Ожидание результата (опрос задачи)
        result = None
        for _ in range(15):  # ~30 секунд
            await asyncio.sleep(2)
            async with session.get(f"{API_URL}/api/v1/task/{task_id}", headers=headers) as task_resp:
                if task_resp.status != 200:
                    continue
                task_status = await task_resp.json()
                if task_status["status"] == "success":
                    result = task_status["result"]
                    break
                elif task_status["status"] == "failure":
                    await processing_msg.edit_text(
                        f"❌ Ошибка анализа: {task_status.get('error', 'неизвестная ошибка')}")
                    return

        if not result or result.get("food") == "unknown":
            await processing_msg.edit_text(
                "😕 Не удалось распознать блюдо на фото.\n"
                "Попробуйте сделать более чёткое фото при хорошем освещении."
            )
            # Всё равно сохраняем как отрицательный пример? По желанию. Пока пропускаем.
            return

        # --- Успешное распознавание: показываем результат и кнопки ---
        response_text = (
            f"🍽️ *Блюдо:* {result['food']}\n"
            f"⚖️ *Вес:* {result['weight_g']} г\n"
            f"🔥 *Калории:* {result['calories']} ккал\n"
            f"🥩 *Белки:* {result['protein_g']} г\n"
            f"🧈 *Жиры:* {result['fat_g']} г\n"
            f"🍚 *Углеводы:* {result['carbs_g']} г\n"
            f"📊 *Уверенность:* {result['confidence'] * 100:.0f}%"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Верно", callback_data=f"correct_{task_id}")],
            [InlineKeyboardButton(text="✏️ Исправить", callback_data=f"fix_{task_id}")]
        ])

        await processing_msg.edit_text(response_text, parse_mode="Markdown", reply_markup=keyboard)

        # Сохраняем данные в FSM для последующего исправления
        await state.update_data(
            task_id=task_id,
            original_result=result,
            temp_image_path=str(temp_image_path)
        )


# --- Обработчики callback'ов (кнопки) ---
@dp.callback_query(lambda c: c.data.startswith("correct_"))
async def correct_feedback(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.split("_")[1]
    data = await state.get_data()
    original_result = data.get("original_result")
    temp_image_path = data.get("temp_image_path")

    if temp_image_path and original_result:
        # Сохраняем как положительный пример
        save_training_sample(
            image_path=temp_image_path,
            correct_label=original_result["food"],
            original_result=original_result,
            is_correct=True
        )
        await callback.message.edit_reply_markup(reply_markup=None)  # убираем кнопки
        await callback.answer("Спасибо за подтверждение! Это поможет улучшить модель.")
    else:
        await callback.answer("Ошибка: данные не найдены.")

    # Удаляем временный файл
    if temp_image_path and Path(temp_image_path).exists():
        Path(temp_image_path).unlink()
    await state.clear()


@dp.callback_query(lambda c: c.data.startswith("fix_"))
async def fix_feedback(callback: CallbackQuery, state: FSMContext):
    task_id = callback.data.split("_")[1]
    await callback.message.edit_text("✏️ Напишите правильное название блюда (одной строкой):")
    await state.set_state(FeedbackState.waiting_for_correction)
    await state.update_data(task_id=task_id)
    await callback.answer()


@dp.message(FeedbackState.waiting_for_correction)
async def receive_correction(message: Message, state: FSMContext):
    correct_name = message.text.strip()
    if len(correct_name) < 3:
        await message.answer("Название должно быть длиннее 2 символов. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    original_result = data.get("original_result")
    temp_image_path = data.get("temp_image_path")

    if temp_image_path and original_result:
        save_training_sample(
            image_path=temp_image_path,
            correct_label=correct_name,
            original_result=original_result,
            is_correct=False
        )
        await message.answer(f"✅ Спасибо! Исправление «{correct_name}» сохранено. Это поможет улучшить модель.")
    else:
        await message.answer("❌ Ошибка: не найден исходный файл. Попробуйте отправить фото заново.")

    # Очистка
    if temp_image_path and Path(temp_image_path).exists():
        Path(temp_image_path).unlink()
    await state.clear()


# --- Запуск бота ---
async def main():
    logger.info("Starting Telegram bot with feedback collection...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is not set!")
        sys.exit(1)
    asyncio.run(main())