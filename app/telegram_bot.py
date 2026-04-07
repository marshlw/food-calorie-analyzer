import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

import aiohttp
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://api:8000")

# ✅ ЕДИНАЯ ПАПКА
UPLOAD_DIR = Path("/app/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

bot = Bot(token=TOKEN)
dp = Dispatcher()


def format_result(result):
    return (
        f"🍽️ {result['food']}\n\n"
        f"⚖️ Вес: {result['weight_g']} г\n"
        f"🔥 Калории: {result['calories']} ккал\n\n"
        f"🥩 Белки: {result['protein_g']} г\n"
        f"🧈 Жиры: {result['fat_g']} г\n"
        f"🍚 Углеводы: {result['carbs_g']} г\n\n"
        f"📊 Уверенность: {result.get('confidence', 0)*100:.0f}%"
    )


@dp.message(Command("start"))
async def start(msg: Message):
    await msg.answer("📸 Отправь фото еды — я посчитаю КБЖУ")


@dp.message(lambda m: m.photo)
async def handle_photo(message: Message):
    msg = await message.answer("🔍 Анализирую...")

    try:
        photo = message.photo[-1]
        file = await bot.get_file(photo.file_id)

        file_path = UPLOAD_DIR / f"{uuid4()}.jpg"

        # ✅ сразу сохраняем туда, где читает celery
        await bot.download_file(file.file_path, destination=file_path)

        async with aiohttp.ClientSession() as session:
            # --- SEND ---
            with open(file_path, "rb") as img:
                form = aiohttp.FormData()
                form.add_field("file", img, filename="img.jpg")

                async with session.post(
                    f"{API_URL}/api/v1/analyze",
                    data=form
                ) as r:
                    task = await r.json()

            task_id = task["id"]

            # --- POLLING ---
            result = None
            delay = 1

            for _ in range(20):
                await asyncio.sleep(delay)
                delay = min(delay * 1.5, 5)

                async with session.get(
                    f"{API_URL}/api/v1/task/{task_id}"
                ) as r:
                    data = await r.json()

                    if data["status"] == "success":
                        result = data["result"]
                        break

            if not result:
                await msg.edit_text("❌ Не удалось обработать изображение")
                return

            await msg.edit_text(format_result(result))

    except Exception as e:
        logging.exception(e)
        await msg.edit_text("❌ Ошибка при обработке")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    if not TOKEN:
        print("No TELEGRAM_BOT_TOKEN")
        sys.exit(1)

    asyncio.run(main())