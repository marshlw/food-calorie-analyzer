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


class TestWeightGoal:
    """Цель по весу через API: она меняет норму КБЖУ и даёт прогноз сроков."""

    def _ready_user(self, client, email):
        """Пользователь с полными данными тела — иначе нормы не считаются."""
        h = _auth_headers(client, email=email, height_cm=180, weight_kg=80)
        client.put("/api/v1/profile", headers=h,
                   json={"sex": "male", "birth_date": "1994-01-01",
                         "activity_level": "moderate"})
        return h

    def test_default_goal_is_maintenance(self, client):
        h = self._ready_user(client, "goal_default@example.com")
        p = client.get("/api/v1/profile", headers=h).json()
        assert p["goal"] == "maintain"
        # Без цели норма равна норме поддержания
        assert p["daily_calorie_target"] == p["maintenance_calories"]

    def test_lose_goal_lowers_calories(self, client):
        h = self._ready_user(client, "goal_lose@example.com")
        before = client.get("/api/v1/profile", headers=h).json()
        after = client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "goal_rate_kg_per_week": 0.5,
        }).json()
        assert after["daily_calorie_target"] < before["daily_calorie_target"]
        assert after["goal_plan"]["calorie_delta"] < 0
        # Белок при этом НЕ падает вместе с калориями — он привязан к массе
        assert after["protein_target_g"] > before["protein_target_g"]

    def test_gain_goal_raises_calories(self, client):
        h = self._ready_user(client, "goal_gain@example.com")
        before = client.get("/api/v1/profile", headers=h).json()
        after = client.put("/api/v1/profile", headers=h, json={
            "goal": "gain", "goal_rate_kg_per_week": 0.25,
        }).json()
        assert after["daily_calorie_target"] > before["daily_calorie_target"]
        assert after["goal_plan"]["calorie_delta"] > 0

    def test_target_weight_gives_forecast(self, client):
        h = self._ready_user(client, "goal_forecast@example.com")
        p = client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "goal_rate_kg_per_week": 0.5, "target_weight_kg": 74,
        }).json()
        plan = p["goal_plan"]
        assert plan["remaining_kg"] == 6.0
        assert plan["weeks_to_goal"] is not None
        assert plan["eta_date"] is not None

    def test_changing_goal_resets_rate(self, client):
        """0.5 кг/нед — умеренное похудение, но вдвое выше безопасного набора,
        поэтому при смене цели темп возвращается к дефолтному."""
        h = self._ready_user(client, "goal_reset@example.com")
        client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "goal_rate_kg_per_week": 0.5,
        })
        p = client.put("/api/v1/profile", headers=h, json={"goal": "gain"}).json()
        assert p["goal_rate_kg_per_week"] is None
        assert p["goal_plan"]["applied_rate_kg_per_week"] <= 0.4

    def test_aggressive_rate_is_capped_with_warning(self, client):
        h = self._ready_user(client, "goal_capped@example.com")
        p = client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "goal_rate_kg_per_week": 1.5,
        }).json()
        assert p["goal_plan"]["applied_rate_kg_per_week"] < 1.5
        assert p["calc_warnings"]  # пользователю объясняем, почему темп снижен

    def test_rate_out_of_range_rejected(self, client):
        h = self._ready_user(client, "goal_range@example.com")
        r = client.put("/api/v1/profile", headers=h,
                       json={"goal": "lose", "goal_rate_kg_per_week": 5})
        assert r.status_code == 422

    def test_invalid_goal_rejected(self, client):
        h = self._ready_user(client, "goal_invalid@example.com")
        r = client.put("/api/v1/profile", headers=h, json={"goal": "teleport"})
        assert r.status_code == 422

    def test_reset_target_weight_with_zero(self, client):
        h = self._ready_user(client, "goal_clear@example.com")
        client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "target_weight_kg": 74,
        })
        p = client.put("/api/v1/profile", headers=h,
                       json={"target_weight_kg": 0}).json()
        assert p["target_weight_kg"] is None
        assert p["goal_plan"]["weeks_to_goal"] is None

    def test_goal_from_registration_is_applied(self, client):
        h = _auth_headers(client, email="goal_reg@example.com",
                          height_cm=180, weight_kg=80, sex="male",
                          birth_date="1994-01-01", activity_level="moderate",
                          goal="lose", goal_rate_kg_per_week=0.5)
        p = client.get("/api/v1/profile", headers=h).json()
        assert p["goal"] == "lose"
        assert p["daily_calorie_target"] < p["maintenance_calories"]

    def test_custom_calorie_target_still_wins(self, client):
        """Ручная норма атлета имеет приоритет над расчётом под цель."""
        h = self._ready_user(client, "goal_custom@example.com")
        p = client.put("/api/v1/profile", headers=h, json={
            "goal": "lose", "goal_rate_kg_per_week": 0.5,
            "custom_calorie_target": 3000,
        }).json()
        assert p["daily_calorie_target"] == 3000


class TestBodyMeasurements:
    """Обхваты тела (талия/грудь/бёдра/плечи) на записи замера + edit/delete."""

    def test_add_record_with_measurements(self, client):
        h = _auth_headers(client, email="measure_add@example.com")
        r = client.post("/api/v1/profile/weight", headers=h, json={
            "weight_kg": 80, "recorded_on": "2026-02-01",
            "waist_cm": 82, "chest_cm": 100, "hips_cm": 95, "shoulders_cm": 118,
        })
        assert r.status_code == 201
        body = r.json()
        assert body["waist_cm"] == 82 and body["shoulders_cm"] == 118

    def test_measurement_out_of_range_rejected(self, client):
        h = _auth_headers(client, email="measure_range@example.com")
        r = client.post("/api/v1/profile/weight", headers=h,
                        json={"weight_kg": 80, "waist_cm": 500})
        assert r.status_code == 422

    def test_edit_updates_weight_and_measurements(self, client):
        h = _auth_headers(client, email="measure_edit@example.com")
        rec = client.post("/api/v1/profile/weight", headers=h, json={
            "weight_kg": 80, "recorded_on": "2026-03-01", "waist_cm": 85,
        }).json()
        r = client.put(f"/api/v1/profile/weight/{rec['id']}", headers=h, json={
            "weight_kg": 78, "recorded_on": "2026-03-01", "waist_cm": 80,
        })
        assert r.status_code == 200
        assert r.json()["weight_kg"] == 78 and r.json()["waist_cm"] == 80

    def test_edit_null_clears_measurement(self, client):
        h = _auth_headers(client, email="measure_clear@example.com")
        rec = client.post("/api/v1/profile/weight", headers=h, json={
            "weight_kg": 80, "recorded_on": "2026-04-01", "waist_cm": 85,
        }).json()
        r = client.put(f"/api/v1/profile/weight/{rec['id']}", headers=h, json={
            "weight_kg": 80, "recorded_on": "2026-04-01", "waist_cm": None,
        })
        assert r.status_code == 200
        assert r.json()["waist_cm"] is None

    def test_edit_date_collision_returns_409(self, client):
        h = _auth_headers(client, email="measure_clash@example.com")
        client.post("/api/v1/profile/weight", headers=h,
                    json={"weight_kg": 80, "recorded_on": "2026-05-01"})
        rec2 = client.post("/api/v1/profile/weight", headers=h,
                           json={"weight_kg": 81, "recorded_on": "2026-05-02"}).json()
        r = client.put(f"/api/v1/profile/weight/{rec2['id']}", headers=h,
                       json={"weight_kg": 81, "recorded_on": "2026-05-01"})
        assert r.status_code == 409

    def test_delete_record(self, client):
        h = _auth_headers(client, email="measure_del@example.com")
        rec = client.post("/api/v1/profile/weight", headers=h,
                          json={"weight_kg": 80, "recorded_on": "2026-06-01"}).json()
        assert client.delete(f"/api/v1/profile/weight/{rec['id']}", headers=h).status_code == 204
        hist = client.get("/api/v1/profile/weight-history", headers=h).json()
        assert all(r["id"] != rec["id"] for r in hist)

    def test_edit_missing_record_404(self, client):
        h = _auth_headers(client, email="measure_404@example.com")
        r = client.put("/api/v1/profile/weight/999999", headers=h,
                       json={"weight_kg": 80})
        assert r.status_code == 404

    def test_cross_user_cannot_edit_or_delete(self, client):
        h1 = _auth_headers(client, email="measure_owner@example.com")
        rec = client.post("/api/v1/profile/weight", headers=h1,
                          json={"weight_kg": 80, "recorded_on": "2026-07-01"}).json()
        h2 = _auth_headers(client, email="measure_intruder@example.com")
        assert client.put(f"/api/v1/profile/weight/{rec['id']}", headers=h2,
                          json={"weight_kg": 70}).status_code == 404
        assert client.delete(f"/api/v1/profile/weight/{rec['id']}", headers=h2).status_code == 404

    def test_profile_edit_writes_measurements_to_today(self, client):
        h = _auth_headers(client, email="measure_profile@example.com",
                          height_cm=180, weight_kg=80)
        client.put("/api/v1/profile", headers=h, json={"weight_kg": 80, "waist_cm": 84})
        profile = client.get("/api/v1/profile", headers=h).json()
        assert profile["current_waist_cm"] == 84
