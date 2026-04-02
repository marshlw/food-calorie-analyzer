import gradio as gr
import requests
import json
from typing import Dict, Any
from .config import settings
import logging
logger = logging.getLogger(__name__)
API_URL = settings.API_URL or "http://localhost:8000"


def analyze_via_api(image_path: str) -> Dict[str, Any]:
    """Отправляет изображение на API и возвращает результат"""
    try:
        with open(image_path, "rb") as f:
            files = {"file": (Path(image_path).name, f, "image/jpeg")}
            response = requests.post(
                f"{API_URL}/api/v1/analyze",
                files=files,
                timeout=30
            )

        if response.status_code == 200:
            task_data = response.json()
            task_id = task_data["task_id"]

            # Опрашиваем задачу (в реальности лучше WebSocket)
            import time
            for _ in range(10):  # 10 попыток
                task_response = requests.get(f"{API_URL}/api/v1/task/{task_id}")
                if task_response.status_code == 200:
                    task_result = task_response.json()
                    if task_result["status"] in ["success", "failure"]:
                        return task_result
                time.sleep(1)

            return {"error": "timeout", "detail": "Analysis took too long"}
        else:
            return {"error": "api_error", "detail": response.text}

    except Exception as e:
        return {"error": "request_failed", "detail": str(e)}


# Gradio интерфейс
demo = gr.Interface(
    fn=analyze_via_api,
    inputs=gr.Image(type="filepath", label="Загрузите фото еды"),
    outputs=gr.JSON(label="Результат анализа"),
    title="🍎 Калории по фото (API)",
    description=f"Backend: {API_URL}",
    examples=[
        ["examples/pasta.jpg"],
        ["examples/salad.jpg"],
    ]
)

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)