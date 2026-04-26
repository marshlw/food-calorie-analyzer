# training_data/generate_dataset.py
import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта модулей app
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Feedback
from app.config import settings

OUTPUT_MODELFILE = Path(__file__).parent / "Modelfile"
BASE_MODEL = settings.MODEL_NAME  # Используем текущую модель из config

def main():
    db = SessionLocal()
    try:
        # Берём все необработанные фидбеки
        feedbacks = db.query(Feedback).filter(Feedback.status == "pending").all()
        if not feedbacks:
            print("Нет новых фидбеков для обучения.")
            return

        # Создаём директорию для изображений если нужно
        images_dir = Path(__file__).parent / "images"
        images_dir.mkdir(exist_ok=True)

        # Генерируем текстовые примеры для SYSTEM-промпта
        examples = []
        for fb in feedbacks[:20]:  # ограничим количество
            examples.append(f"- Блюдо: {fb.corrected_food}, вес: {fb.corrected_weight} г")

            # Копируем изображение для датасета
            src_path = Path(fb.image_path)
            if src_path.exists():
                dst_path = images_dir / f"{fb.id}_{src_path.name}"
                try:
                    import shutil
                    shutil.copy2(src_path, dst_path)
                except Exception as e:
                    print(f"Failed to copy image {src_path}: {e}")

        # Собираем Modelfile
        system_prompt = (
            "Ты AI-ассистент для анализа еды на фото. Твоя задача:"
            "1. Точно определить название блюда"
            "2. Перечислить основные ингредиенты (максимум 5-6)"
            "3. Дать уверенность в предсказании"
            "Верни СТРОГО JSON, БЕЗ MARKDOWN:"
            '{"food": "точное название блюда на русском", "ingredients": [{"name": "основной ингредиент", "type": "protein|carb|fat|vegetable"}], "confidence": 0.0}'
            "ПРАВИЛА:"
            "- Перечисли ТОЛЬКО видимые ингредиенты (максимум 6)"
            "- Не добавляй лишнего или неправдоподобного"
            "- Типизируй ингредиенты для лучшей калорийности"
            "- confidence: 0.95 если уверен, 0.5 если сомневаешься, 0.2 если неясно"
            "- Если это блюдо ты видишь впервые, ставь confidence 0.3-0.5"
            "- Возвращай ТОЛЬКО JSON, БЕЗ текста и markdown кода"
            "\nПримеры правильных ответов из пользовательских исправлений:\n" +
            "\n".join(examples)
        )

        modelfile_content = f"""FROM {BASE_MODEL}
SYSTEM \"\"\"{system_prompt}\"\"\"
PARAMETER temperature 0.2
"""

        with open(OUTPUT_MODELFILE, "w", encoding="utf-8") as f:
            f.write(modelfile_content)

        print(f"Modelfile сохранён в {OUTPUT_MODELFILE}")
        print("Теперь выполните команду:")
        print(f"  ollama create mymodel-improved -f {OUTPUT_MODELFILE}")

        # Помечаем использованные фидбеки
        for fb in feedbacks:
            fb.status = "used"
        db.commit()

    finally:
        db.close()

if __name__ == "__main__":
    main()