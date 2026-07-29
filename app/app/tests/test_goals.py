"""Тесты «Целей»: правила геймификации (app/goals.py) и ручки /api/v1/goals/*.

Стиль повторяет test_profile.py: TestClient + хелпер register/login.
Правила проверяем юнит-тестами напрямую — модуль чистый, БД не нужна.
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
from app import goals


@pytest.fixture
def client():
    return TestClient(app)


def _auth_headers(client, email="goals@example.com", **extra):
    payload = {"email": email, "password": "password123", **extra}
    client.post("/api/v1/register", json=payload)
    tok = client.post(
        "/api/v1/login",
        json={"email": email, "password": "password123", "grant_type": "password"},
    ).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


# ==================== ПРАВИЛА (чистый модуль) ====================

class TestGoalRules:
    def test_plural_ru(self):
        assert goals.days_word(1) == "день"
        assert goals.days_word(2) == "дня"
        assert goals.days_word(5) == "дней"
        assert goals.days_word(11) == "дней"   # 11, а не «1»
        assert goals.days_word(21) == "день"
        assert goals.days_word(112) == "дней"  # 112, а не «2»

    def test_goals_close_on_facts(self):
        items = goals.build_daily_goals(
            meals_count=3,
            water_ml=1800,
            water_target_ml=1800,
            protein_g=120,
            protein_target_g=130,
        )
        by_id = {g.id: g for g in items}
        assert by_id[goals.GOAL_MEALS].done is True
        assert by_id[goals.GOAL_WATER].done is True
        # 120 из 130 = 92% >= порога 90%
        assert by_id[goals.GOAL_PROTEIN].done is True
        assert goals.resolve_status(items, day=date.today()) == goals.STATUS_CLOSED

    def test_partial_and_missed(self):
        partial = goals.build_daily_goals(
            meals_count=3, water_ml=0, water_target_ml=1800,
            protein_g=10, protein_target_g=130,
        )
        assert goals.resolve_status(partial, day=date.today()) == goals.STATUS_PARTIAL

        empty = goals.build_daily_goals(
            meals_count=0, water_ml=0, water_target_ml=1800,
            protein_g=0, protein_target_g=130,
        )
        assert goals.resolve_status(empty, day=date.today()) == goals.STATUS_MISSED

    def test_targets_missing_do_not_block_closing(self):
        """Пустой профиль: норм воды/белка нет — день закрывается по приёмам."""
        items = goals.build_daily_goals(
            meals_count=3, water_ml=0, water_target_ml=None,
            protein_g=0, protein_target_g=None,
        )
        assert [g.id for g in items if g.available] == [goals.GOAL_MEALS]
        assert goals.resolve_status(items, day=date.today()) == goals.STATUS_CLOSED

    def test_frozen_and_future_statuses(self):
        empty = goals.build_daily_goals(
            meals_count=0, water_ml=0, water_target_ml=1800,
            protein_g=0, protein_target_g=130,
        )
        today = date.today()
        assert goals.resolve_status(empty, frozen=True, day=today, today=today) == goals.STATUS_FROZEN
        tomorrow = today + timedelta(days=1)
        assert goals.resolve_status(empty, day=tomorrow, today=today) == goals.STATUS_FUTURE

    def test_sparks_sum_rewards_of_done_goals(self):
        items = goals.build_daily_goals(
            meals_count=3, water_ml=1800, water_target_ml=1800,
            protein_g=0, protein_target_g=130,
        )
        expected = goals.GOAL_SPARKS[goals.GOAL_MEALS] + goals.GOAL_SPARKS[goals.GOAL_WATER]
        assert goals.count_sparks(items) == expected

    def test_streak_counts_back_from_today(self):
        today = date(2026, 7, 29)
        statuses = {
            today: goals.STATUS_CLOSED,
            today - timedelta(days=1): goals.STATUS_CLOSED,
            today - timedelta(days=2): goals.STATUS_FROZEN,
            today - timedelta(days=3): goals.STATUS_PARTIAL,  # обрыв
            today - timedelta(days=4): goals.STATUS_CLOSED,
        }
        assert goals.compute_streak(statuses, today) == 3

    def test_open_today_does_not_break_streak(self):
        """Сегодня ещё идёт — незакрытый день серию не обнуляет."""
        today = date(2026, 7, 29)
        statuses = {
            today: goals.STATUS_PARTIAL,
            today - timedelta(days=1): goals.STATUS_CLOSED,
            today - timedelta(days=2): goals.STATUS_CLOSED,
        }
        assert goals.compute_streak(statuses, today) == 2

    def test_missing_yesterday_breaks_streak(self):
        today = date(2026, 7, 29)
        statuses = {today: goals.STATUS_CLOSED}  # вчера записи нет = пропуск
        assert goals.compute_streak(statuses, today) == 1

    def test_best_streak_over_history(self):
        start = date(2026, 6, 1)
        statuses = {}
        for i in range(5):
            statuses[start + timedelta(days=i)] = goals.STATUS_CLOSED
        statuses[start + timedelta(days=5)] = goals.STATUS_MISSED
        for i in range(6, 9):
            statuses[start + timedelta(days=i)] = goals.STATUS_CLOSED
        assert goals.compute_best_streak(statuses) == 5

    def test_milestones_on_streak_position(self):
        assert goals.milestone_for(7) == "7 дней"
        assert goals.milestone_for(30) == "месяц"
        assert goals.milestone_for(8) is None

    def test_rewards_stay_reached_after_streak_breaks(self):
        rewards = {r["code"]: r for r in goals.build_rewards(streak=0, best_streak=14)}
        assert rewards["week"]["reached"] is True
        assert rewards["two_weeks"]["reached"] is True
        assert rewards["month"]["reached"] is False

    def test_can_freeze_rules(self):
        today = date(2026, 7, 29)
        yesterday = today - timedelta(days=1)

        assert goals.can_freeze(yesterday, today, goals.STATUS_MISSED, 1) is None
        assert goals.can_freeze(yesterday, today, goals.STATUS_MISSED, 0) is not None
        assert goals.can_freeze(today, today, goals.STATUS_MISSED, 1) is not None
        assert goals.can_freeze(today + timedelta(days=1), today, goals.STATUS_FUTURE, 1) is not None
        assert goals.can_freeze(yesterday, today, goals.STATUS_CLOSED, 1) is not None
        old = today - timedelta(days=goals.FREEZE_MAX_AGE_DAYS + 1)
        assert goals.can_freeze(old, today, goals.STATUS_MISSED, 1) is not None


# ==================== РУЧКИ ====================

class TestGoalsApi:
    def test_today_returns_three_goals_for_fresh_user(self, client):
        h = _auth_headers(client, email="goals_today@example.com",
                          height_cm=180, weight_kg=80)
        data = client.get("/api/v1/goals/today", headers=h).json()

        assert len(data["goals"]) == 3
        assert data["streak"] == 0
        assert data["done_count"] == 0
        assert data["day_closed"] is False
        assert len(data["week"]) == 7
        assert data["freezes_available"] == goals.DEFAULT_FREEZES

    def test_meals_goal_closes_after_three_entries(self, client):
        h = _auth_headers(client, email="goals_meals@example.com",
                          height_cm=180, weight_kg=80)
        for i in range(goals.MEALS_TARGET):
            client.post(
                "/api/v1/meals",
                headers=h,
                json={
                    "food_name": f"Блюдо {i}",
                    "calories": 300, "protein_g": 20,
                    "fat_g": 10, "carbs_g": 30, "weight_g": 200,
                    "meal_type": "lunch",
                },
            )

        data = client.get("/api/v1/goals/today", headers=h).json()
        meals_goal = next(g for g in data["goals"] if g["id"] == goals.GOAL_MEALS)
        assert meals_goal["done"] is True
        assert data["done_count"] >= 1
        assert data["sparks"] >= goals.GOAL_SPARKS[goals.GOAL_MEALS]

    def test_path_returns_month_grid(self, client):
        h = _auth_headers(client, email="goals_path@example.com",
                          height_cm=180, weight_kg=80)
        month = date.today().strftime("%Y-%m")
        data = client.get("/api/v1/goals/path", headers=h, params={"month": month}).json()

        assert data["month"] == month
        assert 28 <= len(data["days"]) <= 31
        assert data["total_days"] == len(data["days"])
        assert len(data["rewards"]) == len(goals.REWARDS)
        # Дни после сегодняшнего помечены как будущие
        future = [d for d in data["days"] if d["day"] > date.today().day]
        assert all(d["status"] == "future" for d in future)

    def test_path_rejects_bad_month(self, client):
        h = _auth_headers(client, email="goals_badmonth@example.com")
        assert client.get("/api/v1/goals/path", headers=h,
                          params={"month": "2026/07"}).status_code == 400

    def test_freeze_spends_one_and_marks_day(self, client):
        h = _auth_headers(client, email="goals_freeze@example.com",
                          height_cm=180, weight_kg=80)
        before = client.get("/api/v1/goals/today", headers=h).json()

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        resp = client.post("/api/v1/goals/freeze", headers=h, json={"date": yesterday})
        assert resp.status_code == 200
        after = resp.json()

        assert after["freezes_available"] == before["freezes_available"] - 1
        # Замороженный вчерашний день продлевает серию
        assert after["streak"] >= 1

    def test_freeze_twice_same_day_rejected(self, client):
        h = _auth_headers(client, email="goals_freeze2@example.com",
                          height_cm=180, weight_kg=80)
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        client.post("/api/v1/goals/freeze", headers=h, json={"date": yesterday})
        second = client.post("/api/v1/goals/freeze", headers=h, json={"date": yesterday})
        assert second.status_code == 400

    def test_goals_require_auth(self, client):
        assert client.get("/api/v1/goals/today").status_code in (401, 403)
        assert client.get("/api/v1/goals/path").status_code in (401, 403)
