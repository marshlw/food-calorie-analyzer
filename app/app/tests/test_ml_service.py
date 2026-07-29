"""
Tests for ML service model fallback chain.

Tests that when a model fails, the system tries the next model in the chain,
and treats fallback as a successful result (not an error).
"""

import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add app directory to path for imports
app_dir = Path(__file__).parent.parent
if str(app_dir) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(app_dir))

from app import ml_service
from app.config import settings


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a sample image file for testing."""
    from PIL import Image
    
    img = Image.new("RGB", (100, 100), color="red")
    img_path = tmp_path / "test_image.jpg"
    img.save(img_path)
    return str(img_path)


class TestModelFallback:
    """Test model fallback chain behavior."""

    def test_gemini_success(self, sample_image_path):
        """Test successful Gemini analysis."""
        mock_response = {
            "food": "pasta carbonara",
            "weight_g": 300,
            "confidence": 0.95,
            "ingredients": [
                {"name": "pasta", "type": "carb"},
                {"name": "bacon", "type": "protein"},
            ],
        }

        with patch.object(ml_service, "call_gemini") as mock_gemini:
            mock_gemini.return_value = json.dumps(mock_response)

            result = ml_service.analyze_image_sync(sample_image_path)

            assert result is not None
            assert result["source"] == "gemini"
            assert result["food"] == "pasta carbonara"
            assert "gemini" in result["models_tried"]
            assert result["processing_time_sec"] > 0

    def test_gemini_fails_deepseek_succeeds(self, sample_image_path):
        """Test Gemini fails and DeepSeek succeeds."""
        mock_deepseek_response = {
            "food": "pizza",
            "weight_g": 250,
            "confidence": 0.88,
            "ingredients": [
                {"name": "cheese", "type": "protein"},
                {"name": "tomato", "type": "vegetable"},
            ],
        }

        with patch.object(ml_service, "call_gemini") as mock_gemini:
            with patch.object(ml_service, "call_deepseek_vision") as mock_deepseek:
                mock_gemini.return_value = None  # Gemini fails
                mock_deepseek.return_value = json.dumps(mock_deepseek_response)

                result = ml_service.analyze_image_sync(sample_image_path)

                assert result is not None
                assert result["source"] == "deepseek"
                assert result["food"] == "pizza"
                assert "gemini" in result["models_tried"]
                assert "deepseek" in result["models_tried"]
                assert result["processing_time_sec"] > 0

    def test_all_models_fail_raises(self, sample_image_path):
        """Отказ ВСЕХ провайдеров должен подниматься наверх.

        Раньше здесь возвращался DEFAULT_FALLBACK ('unknown', 200 ккал), и
        задача помечалась SUCCESS: ретрай не срабатывал, попытка из дневного
        лимита сгорала, а пользователь получал выдуманные цифры.
        """
        with patch.object(ml_service, "call_gemini") as mock_gemini:
            with patch.object(ml_service, "call_deepseek_vision") as mock_deepseek:
                with patch.object(ml_service, "call_ollama_vision") as mock_ollama:
                    mock_gemini.return_value = None
                    mock_deepseek.return_value = None
                    mock_ollama.return_value = None

                    with pytest.raises(ml_service.AnalysisError) as exc_info:
                        ml_service.analyze_image_sync(sample_image_path)

                    # В тексте ошибки — список опробованных провайдеров
                    assert "gemini" in str(exc_info.value)

    def test_missing_file_raises_permanent(self, tmp_path):
        """Отсутствующий файл — ошибка без ретраев."""
        missing = tmp_path / "nope.jpg"
        with pytest.raises(ml_service.AnalysisPermanentError):
            ml_service.analyze_image_sync(str(missing))

    def test_invalid_json_tries_next_model(self, sample_image_path):
        """Test invalid JSON from Gemini triggers DeepSeek."""
        mock_deepseek_response = {
            "food": "salad",
            "weight_g": 200,
            "confidence": 0.85,
            "ingredients": [],
        }

        with patch.object(ml_service, "call_gemini") as mock_gemini:
            with patch.object(ml_service, "call_deepseek_vision") as mock_deepseek:
                mock_gemini.return_value = "invalid json {{{{"  # Invalid JSON
                mock_deepseek.return_value = json.dumps(mock_deepseek_response)

                result = ml_service.analyze_image_sync(sample_image_path)

                assert result is not None
                assert result["source"] == "deepseek"
                assert result["food"] == "salad"

    def test_result_structure_includes_metadata(self, sample_image_path):
        """Test result includes source, models_tried, and processing_time_sec."""
        mock_response = {
            "food": "burger",
            "weight_g": 150,
            "confidence": 0.9,
            "ingredients": [],
        }

        with patch.object(ml_service, "call_gemini") as mock_gemini:
            mock_gemini.return_value = json.dumps(mock_response)

            result = ml_service.analyze_image_sync(sample_image_path)

            assert "source" in result
            assert "models_tried" in result
            assert "processing_time_sec" in result
            assert isinstance(result["processing_time_sec"], float)
            assert result["processing_time_sec"] > 0

    def test_cache_returns_cached_result(self, sample_image_path):
        """Test cached result includes source='cache'."""
        mock_response = {
            "food": "rice",
            "weight_g": 180,
            "confidence": 0.92,
            "ingredients": [],
            "source": "gemini",
            "models_tried": ["gemini"],
        }

        with patch.object(ml_service, "redis_client") as mock_redis:
            cache_key = f"{settings.CACHE_PREFIX}:v8:{ml_service.get_hash(sample_image_path)}"
            mock_redis.get.return_value = json.dumps(mock_response)

            result = ml_service.analyze_image_sync(sample_image_path)

            assert result is not None
            assert result["source"] == "cache"
            mock_redis.get.assert_called()


class TestResponseValidation:
    """Test response validation logic."""

    def test_valid_response(self):
        """Test valid response passes validation."""
        data = {
            "food": "chicken",
            "weight_g": 200,
            "confidence": 0.9,
            "ingredients": [{"name": "chicken", "type": "protein"}],
        }
        assert ml_service.validate_response(data) is True

    def test_missing_food_fails(self):
        """Test missing food field fails validation."""
        data = {
            "weight_g": 200,
            "confidence": 0.9,
            "ingredients": [],
        }
        assert ml_service.validate_response(data) is False

    def test_weight_out_of_range_fails(self):
        """Test weight outside range fails."""
        data = {
            "food": "food",
            "weight_g": 10,  # Below min 50
            "confidence": 0.9,
            "ingredients": [],
        }
        assert ml_service.validate_response(data) is False

    def test_confidence_out_of_range_fails(self):
        """Test confidence outside 0-1 range fails."""
        data = {
            "food": "food",
            "weight_g": 200,
            "confidence": 1.5,  # Above max 1.0
            "ingredients": [],
        }
        assert ml_service.validate_response(data) is False

    def test_too_many_ingredients_fails(self):
        """Test more than 6 ingredients fails."""
        data = {
            "food": "food",
            "weight_g": 200,
            "confidence": 0.9,
            "ingredients": [
                {"name": f"ing{i}", "type": "carb"} for i in range(7)
            ],
        }
        assert ml_service.validate_response(data) is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
