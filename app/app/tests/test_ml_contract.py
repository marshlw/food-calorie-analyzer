import pytest
from ml_service import analyze_image
from schemas import NutritionResponse


@pytest.mark.integration
def test_qwen_food_recognition():
    """Интеграционный тест с реальной моделью"""
    result = analyze_image("tests/fixtures/pasta.jpg")

    # Проверка схемы
    assert "error" not in result
    resp = NutritionResponse.model_validate(result)

    # Бизнес-проверки
    assert resp.calories > 0
    assert resp.weight_g > 0
    assert resp.confidence >= 0.5
    assert "паста" in resp.food.lower() or "макароны" in resp.food.lower()


@pytest.mark.unit
def test_error_handling_missing_file():
    result = analyze_image("nonexistent.jpg")
    assert "error" in result