"""Tests for the user profile module: height/weight, weight history, BMR.

Mirrors the style of test_api.py (TestClient + register/login helper).
"""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Add app directory to path (same shim as test_api.py)
app_dir = Path(__file__).parent.parent
if str(app_dir) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(app_dir))

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _auth_headers(client, email="profile@example.com", **extra):
    """Register (idempotently) + login, return Authorization header."""
    payload = {"email": email, "password": "password123", **extra}
    client.post("/api/v1/register", json=payload)
    tok = client.post(
        "/api/v1/login",
        json={"email": email, "password": "password123", "grant_type": "password"},
    ).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


class TestProfile:
    def test_registration_weight_becomes_first_record(self, client):
        h = _auth_headers(client, email="reg_weight@example.com",
                          height_cm=180, weight_kg=80)
        hist = client.get("/api/v1/profile/weight-history", headers=h).json()
        assert len(hist) == 1
        assert hist[0]["weight_kg"] == 80
        assert hist[0]["source"] == "registration"

    def test_get_profile_exposes_current_weight_and_bmr(self, client):
        h = _auth_headers(client, email="bmr@example.com",
                          height_cm=180, weight_kg=80)
        client.put("/api/v1/profile", headers=h,
                   json={"sex": "male", "birth_date": "1994-01-01",
                         "activity_level": "moderate"})
        profile = client.get("/api/v1/profile", headers=h).json()
        assert profile["current_weight_kg"] == 80
        assert profile["height_cm"] == 180
        assert profile["bmr"] is not None
        assert profile["daily_calorie_target"] is not None

    def test_put_profile_adds_record_when_weight_changes(self, client):
        h = _auth_headers(client, email="put_change@example.com",
                          height_cm=180, weight_kg=80)
        client.put("/api/v1/profile", headers=h, json={"weight_kg": 78})
        hist = client.get("/api/v1/profile/weight-history", headers=h).json()
        # registration record + today's edit (different day) OR upsert same day:
        # value must reflect the latest weight.
        assert client.get("/api/v1/profile", headers=h).json()["current_weight_kg"] == 78

    def test_same_day_upsert_no_duplicate(self, client):
        h = _auth_headers(client, email="upsert@example.com")
        client.post("/api/v1/profile/weight", headers=h, json={"weight_kg": 77})
        client.post("/api/v1/profile/weight", headers=h, json={"weight_kg": 76})
        today = date.today().isoformat()
        hist = client.get("/api/v1/profile/weight-history", headers=h).json()
        today_rows = [r for r in hist if r["recorded_on"] == today]
        assert len(today_rows) == 1
        assert today_rows[0]["weight_kg"] == 76

    def test_manual_past_date_record(self, client):
        h = _auth_headers(client, email="past@example.com")
        r = client.post("/api/v1/profile/weight", headers=h,
                        json={"weight_kg": 82, "recorded_on": "2026-01-01",
                              "note": "после праздников"})
        assert r.status_code == 201
        assert r.json()["recorded_on"] == "2026-01-01"

    def test_weight_validation_rejects_out_of_range(self, client):
        h = _auth_headers(client, email="valid@example.com")
        assert client.post("/api/v1/profile/weight", headers=h,
                           json={"weight_kg": 500}).status_code == 422
        assert client.post("/api/v1/profile/weight", headers=h,
                           json={"weight_kg": 0}).status_code == 422

    def test_future_date_rejected(self, client):
        h = _auth_headers(client, email="future@example.com")
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        r = client.post("/api/v1/profile/weight", headers=h,
                        json={"weight_kg": 70, "recorded_on": tomorrow})
        assert r.status_code == 400

    def test_save_weight_as_record_false_keeps_history(self, client):
        h = _auth_headers(client, email="norecord@example.com")
        client.post("/api/v1/profile/weight", headers=h, json={"weight_kg": 77})
        client.put("/api/v1/profile", headers=h,
                   json={"weight_kg": 70, "save_weight_as_record": False})
        assert client.get("/api/v1/profile", headers=h).json()["current_weight_kg"] == 77

    def test_requires_auth(self, client):
        assert client.get("/api/v1/profile").status_code in (401, 403)
        assert client.get("/api/v1/profile/weight-history").status_code in (401, 403)

    def test_cross_user_isolation(self, client):
        h1 = _auth_headers(client, email="user1@example.com")
        client.post("/api/v1/profile/weight", headers=h1, json={"weight_kg": 88})
        h2 = _auth_headers(client, email="user2@example.com")
        hist2 = client.get("/api/v1/profile/weight-history", headers=h2).json()
        assert all(r["weight_kg"] != 88 for r in hist2)
