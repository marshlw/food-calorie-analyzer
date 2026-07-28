"""Юнит-тесты расчёта норм КБЖУ под цель (app/nutrition.py).

Модуль чистый (без БД и HTTP), поэтому тестируется напрямую — быстро и без
фикстур. Проверяем не «магические числа», а инварианты, ради которых расчёт
и переписывался: направление поправки, работу ограничителей безопасности,
согласованность прогноза с выданной нормой и вменяемость БЖУ на краях.
"""

from datetime import date

import pytest

from app import nutrition as n


# Типовой профиль: мужчина 30 лет, 180 см, 80 кг, средняя активность.
BASE = dict(weight_kg=80.0, height_cm=180.0, age=30, sex="male",
            activity_level="moderate")


def plan(**overrides):
    return n.build_plan(**{**BASE, **overrides})


def codes(p) -> set:
    return {w["code"] for w in p.warnings}


class TestBmrTdee:
    def test_mifflin_male(self):
        # 10*80 + 6.25*180 - 5*30 + 5 = 1780
        assert n.calc_bmr(80, 180, 30, "male") == 1780.0

    def test_mifflin_female(self):
        # то же тело, но -161 вместо +5
        assert n.calc_bmr(80, 180, 30, "female") == 1614.0

    def test_missing_data_returns_none(self):
        assert n.calc_bmr(None, 180, 30, "male") is None
        assert n.calc_bmr(80, 180, None, "male") is None
        assert n.calc_bmr(80, 180, 30, None) is None

    def test_zero_age_is_valid(self):
        """age=0 — не «нет данных»: старая реализация на all([...]) его теряла."""
        assert n.calc_bmr(10, 75, 0, "male") is not None

    def test_tdee_uses_activity_factor(self):
        assert n.calc_tdee(1780, "moderate") == round(1780 * 1.55)
        # Неизвестный уровень -> самый консервативный множитель
        assert n.calc_tdee(1780, "bogus") == n.calc_tdee(1780, "sedentary")


class TestGoalDirection:
    def test_maintain_equals_tdee(self):
        p = plan(goal="maintain")
        assert p.calories == p.tdee
        assert p.goal_plan.calorie_delta == 0

    def test_lose_is_deficit(self):
        p = plan(goal="lose", goal_rate_kg_per_week=0.5)
        assert p.calories < p.tdee
        assert p.goal_plan.calorie_delta < 0

    def test_gain_is_surplus(self):
        p = plan(goal="gain", goal_rate_kg_per_week=0.25)
        assert p.calories > p.tdee
        assert p.goal_plan.calorie_delta > 0

    def test_deficit_matches_energy_equivalent(self):
        """0.5 кг/нед x 7700 ккал / 7 дней ~ 550 ккал/сут."""
        p = plan(goal="lose", goal_rate_kg_per_week=0.5)
        assert p.goal_plan.calorie_delta == pytest.approx(-550, abs=2)

    def test_faster_rate_means_bigger_deficit(self):
        slow = plan(goal="lose", goal_rate_kg_per_week=0.25)
        fast = plan(goal="lose", goal_rate_kg_per_week=0.5)
        assert fast.calories < slow.calories

    def test_unknown_goal_falls_back_to_maintain(self):
        p = plan(goal="ЖЕЛЕЗНЫЙ_ЧЕЛОВЕК")
        assert p.calories == p.tdee

    def test_none_goal_keeps_legacy_behaviour(self):
        """Существующие пользователи (goal=NULL) получают прежнюю норму = TDEE."""
        p = plan(goal=None)
        assert p.calories == p.tdee


class TestGuardrails:
    def test_rate_capped_by_body_weight(self):
        """Похудение быстрее 1% массы в неделю урезается (80 кг -> 0.8 кг/нед)."""
        p = plan(goal="lose", goal_rate_kg_per_week=1.5)
        assert n.W_RATE_CAPPED in codes(p)
        assert p.goal_plan.applied_rate_kg_per_week <= 0.8

    def test_gain_rate_capped_tighter(self):
        """Для набора потолок вдвое ниже: быстрее — прибавка идёт в жир."""
        p = plan(goal="gain", goal_rate_kg_per_week=1.0)
        assert n.W_RATE_CAPPED in codes(p)
        assert p.goal_plan.applied_rate_kg_per_week <= 0.4

    def test_calories_never_below_bmr(self):
        """Хрупкая женщина + агрессивный темп: норма упирается в базовый обмен."""
        p = plan(weight_kg=50, height_cm=155, age=45, sex="female",
                 activity_level="sedentary", goal="lose",
                 goal_rate_kg_per_week=1.5)
        assert p.calories >= p.bmr

    def test_absolute_floor_respected(self):
        p = plan(weight_kg=45, height_cm=150, age=60, sex="female",
                 activity_level="sedentary", goal="lose",
                 goal_rate_kg_per_week=1.5)
        assert p.calories >= n.MIN_CALORIES_BY_SEX["female"]

    def test_deficit_never_exceeds_quarter_of_tdee(self):
        for weight in (50, 60, 80, 100, 140):
            p = plan(weight_kg=weight, goal="lose", goal_rate_kg_per_week=1.5)
            assert p.calories >= p.tdee * (1 - n.MAX_DEFICIT_FRACTION) - 1

    def test_surplus_capped(self):
        p = plan(weight_kg=120, goal="gain", goal_rate_kg_per_week=1.5)
        assert p.calories <= p.tdee * (1 + n.MAX_SURPLUS_FRACTION) + 1


class TestForecast:
    def test_forecast_matches_applied_rate(self):
        """Обещанный срок должен следовать из ФАКТИЧЕСКОГО темпа, иначе
        пользователь получит норму под 0.8 кг/нед, а прогноз под 1.5."""
        p = plan(goal="lose", goal_rate_kg_per_week=1.5, target_weight_kg=70)
        gp = p.goal_plan
        assert gp.remaining_kg == 10.0
        assert gp.weeks_to_goal == pytest.approx(
            gp.remaining_kg / gp.applied_rate_kg_per_week, abs=0.15
        )

    def test_eta_is_in_the_future(self):
        today = date(2026, 1, 1)
        p = n.build_plan(**BASE, goal="lose", goal_rate_kg_per_week=0.5,
                         target_weight_kg=75, today=today)
        assert p.goal_plan.eta_date > today

    def test_no_target_means_no_forecast(self):
        p = plan(goal="lose", goal_rate_kg_per_week=0.5)
        assert p.goal_plan.weeks_to_goal is None
        assert p.goal_plan.eta_date is None

    def test_target_reached_switches_to_maintenance(self):
        p = plan(goal="lose", goal_rate_kg_per_week=0.5, target_weight_kg=79.8)
        assert n.W_GOAL_REACHED in codes(p)
        assert p.calories == p.tdee
        assert p.goal_plan.reached is True

    def test_target_conflicting_with_goal_is_flagged(self):
        """Цель «похудеть», а целевой вес выше текущего — прогноз не строим."""
        p = plan(goal="lose", goal_rate_kg_per_week=0.5, target_weight_kg=90)
        assert n.W_TARGET_CONFLICTS_GOAL in codes(p)
        assert p.goal_plan.weeks_to_goal is None
        # Но саму норму под цель всё равно выдаём
        assert p.calories < p.tdee


class TestMacros:
    def test_macros_sum_to_calories(self):
        for goal in ("lose", "maintain", "gain"):
            p = plan(goal=goal)
            total = (p.protein_g * 4 + p.fat_g * 9 + p.carbs_g * 4)
            assert total == pytest.approx(p.calories, rel=0.03)

    def test_protein_scales_with_body_not_calories(self):
        """Ключевое отличие от старого расчёта: белок привязан к массе тела,
        поэтому в дефиците он не падает вместе с калориями."""
        maintain = plan(goal="maintain")
        lose = plan(goal="lose", goal_rate_kg_per_week=0.5)
        assert lose.calories < maintain.calories
        assert lose.protein_g > maintain.protein_g

    def test_protein_within_physiological_range(self):
        for goal in ("lose", "maintain", "gain"):
            for activity in n.ACTIVITY_LEVELS:
                p = plan(goal=goal, activity_level=activity)
                g_per_kg = p.protein_g / p.reference_weight_kg
                assert n.PROTEIN_G_PER_KG_MIN - 0.05 <= g_per_kg <= n.PROTEIN_G_PER_KG_MAX + 0.05

    def test_fat_never_below_hormonal_floor(self):
        p = plan(goal="lose", goal_rate_kg_per_week=1.5)
        assert p.fat_g >= p.reference_weight_kg * n.FAT_G_PER_KG_FLOOR - 1

    def test_obesity_uses_adjusted_weight(self):
        """140 кг при 170 см (ИМТ ~48): от фактической массы белок вышел бы
        ~266 г. Скорректированная масса держит норму в разумных пределах."""
        p = plan(weight_kg=140, height_cm=170, goal="lose",
                 goal_rate_kg_per_week=1.0)
        assert p.reference_weight_kg < 140
        # Меньше 1.5 г на КАЖДЫЙ фактический килограмм — то, что и нужно
        assert p.protein_g / 140 < 1.5

    def test_normal_bmi_uses_actual_weight(self):
        p = plan(weight_kg=80, height_cm=180)
        assert p.reference_weight_kg == 80.0

    def test_macros_rebalance_when_calories_are_tight(self):
        """95 кг при 180 см (ИМТ 29 — скидки на ожирение нет) + жёсткий
        дефицит: белок и жир по норме съели бы почти все калории.
        Расчёт должен ужать их, а не выдать отрицательные углеводы."""
        p = plan(weight_kg=95, height_cm=180, age=60, sex="female",
                 activity_level="sedentary", goal="lose",
                 goal_rate_kg_per_week=1.5)
        assert p.carbs_g >= n.CARBS_G_MIN - 1
        assert p.fat_g >= p.reference_weight_kg * n.FAT_G_PER_KG_FLOOR - 1
        assert p.protein_g >= p.reference_weight_kg * n.PROTEIN_G_PER_KG_MIN - 1
        # И сумма макросов всё ещё сходится с калорийностью
        assert p.protein_g * 4 + p.fat_g * 9 + p.carbs_g * 4 == pytest.approx(
            p.calories, rel=0.03
        )

    def test_macros_positive_in_extreme_case(self):
        """Большая масса + жёсткий дефицит: макросы не уходят в минус."""
        p = plan(weight_kg=150, height_cm=165, age=55, sex="female",
                 activity_level="sedentary", goal="lose",
                 goal_rate_kg_per_week=1.5)
        assert p.protein_g > 0 and p.fat_g > 0 and p.carbs_g >= 0

    def test_no_weight_falls_back_to_percentages(self):
        macros = n.calc_macro_targets(2000, weight_kg=None)
        assert macros["protein_g"] and macros["fat_g"] and macros["carbs_g"]


class TestWater:
    def test_scales_with_weight_and_activity(self):
        assert n.calc_water_target(80, "sedentary") < n.calc_water_target(80, "very_active")
        assert n.calc_water_target(60, "moderate") < n.calc_water_target(90, "moderate")

    def test_weight_loss_adds_water(self):
        assert n.calc_water_target(80, "moderate", "lose") > \
               n.calc_water_target(80, "moderate", "maintain")

    def test_no_weight_returns_none(self):
        assert n.calc_water_target(None, "moderate") is None


class TestMissingData:
    def test_no_height_no_calories_but_no_crash(self):
        p = plan(height_cm=None)
        assert p.calories is None
        assert p.protein_g is None
        assert n.W_MISSING_DATA in codes(p)
        # Вода считается от одного веса — её отдаём даже без остальных данных
        assert p.water_ml is not None

    def test_goal_plan_present_even_without_numbers(self):
        p = plan(weight_kg=None, height_cm=None, age=None, sex=None, goal="lose")
        assert p.goal_plan is not None
        assert p.goal_plan.goal == "lose"


class TestAgeHelper:
    def test_birthday_not_yet_this_year(self):
        assert n.calc_age(date(1990, 12, 31), today=date(2026, 1, 1)) == 35

    def test_birthday_already_passed(self):
        assert n.calc_age(date(1990, 1, 1), today=date(2026, 1, 1)) == 36

    def test_none_birth_date(self):
        assert n.calc_age(None) is None
