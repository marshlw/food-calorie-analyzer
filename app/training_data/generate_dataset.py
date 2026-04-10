# training_data/generate_dataset.py
import json
import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта модулей app
sys.path.append(str(Path(__file__).parent.parent))

from app.database import SessionLocal
from app.models import Feedback

OUTPUT_MODELFILE = Path(__file__).parent / "Modelfile"
BASE_MODEL = "llava:13b"  # или ваша текущая модель

def main():
    db = SessionLocal()
    try:
        # Берём все необработанные фидбеки
        feedbacks = db.query(Feedback).filter(Feedback.status == "pending").all()
        if not feedbacks:
            print("Нет новых фидбеков для обучения.")
            return

        # Генерируем текстовые примеры для SYSTEM-промпта
        examples = []
        for fb in feedbacks[:20]:  # ограничим количество
            examples.append(f"- Блюдо: {fb.corrected_food}, вес: {fb.corrected_weight} г")

        # Собираем Modelfile
        system_prompt = (
            "Ты эксперт по питанию. Отвечай строго в JSON.\n"
            "Примеры правильных ответов из пользовательских исправлений:\n" +
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