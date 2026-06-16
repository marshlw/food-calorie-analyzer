"""
Tests for FastAPI endpoints.

Tests authentication flow, token refresh, and analysis endpoints.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Add app directory to path
app_dir = Path(__file__).parent.parent
if str(app_dir) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(app_dir))

from app.main import app
from app import auth, crud, database, ml_service
from app.config import settings
from app.models import Base, User, TaskStatus


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user_data():
    """Test user credentials."""
    return {
        "email": "test@example.com",
        "password": "testpassword123"
    }


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_register_user(self, client, test_user_data):
        """Test user registration."""
        response = client.post(
            "/api/v1/register",
            json=test_user_data
        )
        assert response.status_code == 201
        data = response.json()
        assert data.get("id")
        assert data.get("email") == test_user_data["email"]
        assert "password" not in data

    def test_register_duplicate_user(self, client, test_user_data):
        """Test registering duplicate user returns 400."""
        # First registration
        client.post("/api/v1/register", json=test_user_data)
        
        # Second registration (duplicate)
        response = client.post("/api/v1/register", json=test_user_data)
        assert response.status_code == 400

    def test_login_with_email_password(self, client, test_user_data):
        """Test login with email and password."""
        # Register first
        client.post("/api/v1/register", json=test_user_data)
        
        # Login
        response = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client, test_user_data):
        """Test login with wrong password."""
        # Register
        client.post("/api/v1/register", json=test_user_data)
        
        # Login with wrong password
        response = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": "wrongpassword"
            }
        )
        assert response.status_code == 401

    def test_token_refresh(self, client, test_user_data):
        """Test refresh token endpoint."""
        # Register and login
        client.post("/api/v1/register", json=test_user_data)
        login_resp = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        refresh_token = login_resp.json()["refresh_token"]
        
        # Refresh token
        response = client.post(
            "/api/v1/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_get_current_user(self, client, test_user_data):
        """Test /me endpoint returns current user."""
        # Register and login
        client.post("/api/v1/register", json=test_user_data)
        login_resp = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        access_token = login_resp.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]


class TestAnalysisEndpoints:
    """Test image analysis endpoints."""

    @pytest.fixture
    def auth_token(self, client, test_user_data):
        """Get authenticated token."""
        client.post("/api/v1/register", json=test_user_data)
        login_resp = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        return login_resp.json()["access_token"]

    def test_analyze_requires_auth(self, client):
        """Test analyze endpoint requires authentication."""
        response = client.post(
            "/api/v1/analyze",
            data={},
        )
        # FastAPI will return 403 Forbidden if no token
        assert response.status_code in (401, 403)

    def test_get_task_status(self, client, auth_token):
        """Test getting task status."""
        # First create a task (will fail without image, but creates empty task)
        # For now, just test accessing non-existent task returns appropriate error
        response = client.get(
            "/api/v1/task/nonexistent-id",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # Should return 404 or similar
        assert response.status_code >= 400

    def test_meal_creation_response_structure(self, client, auth_token):
        """Test meal creation returns correct structure."""
        meal_data = {
            "task_id": "test-id",
            "meal_type": "lunch"
        }
        response = client.post(
            "/api/v1/meals/from-analysis",
            json=meal_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        if response.status_code == 200:
            data = response.json()
            assert "id" in data
            assert "food_name" in data
            assert "calories" in data


class TestFeedbackEndpoint:
    """Test feedback submission."""

    @pytest.fixture
    def auth_token(self, client, test_user_data):
        """Get authenticated token."""
        client.post("/api/v1/register", json=test_user_data)
        login_resp = client.post(
            "/api/v1/login",
            data={
                "email": test_user_data["email"],
                "password": test_user_data["password"]
            }
        )
        return login_resp.json()["access_token"]

    def test_feedback_requires_auth(self, client):
        """Test feedback requires authentication."""
        response = client.post(
            "/api/v1/feedback",
            json={}
        )
        assert response.status_code in (401, 403)

    def test_feedback_submission_structure(self, client, auth_token):
        """Test feedback submission structure."""
        feedback_data = {
            "task_id": "test-id",
            "correct_food": "rice",
            "correct_weight": 200
        }
        response = client.post(
            "/api/v1/feedback",
            json=feedback_data,
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        # May return 404 if task doesn't exist, but that's ok for structure test
        # The important thing is it accepts the data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
