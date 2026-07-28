"""Расчёт суточных норм КБЖУ и воды под ЦЕЛЬ пользователя.

Чистый модуль без зависимостей от БД и FastAPI: на вход — параметры тела и
цель, на выходе — нормы + объяснение, как они получены. Так расчёт легко
тестируется юнит-тестами и переиспользуется из crud/советчика/бота.

Модель расчёта (по шагам)
-------------------------
1. BMR — базовый обмен по формуле Миффлина–Сан-Жеора.
2. TDEE = BMR x коэффициент активности — расход на поддержание веса.
3. Цель -> суточная поправка калорий. Считается не «минус N процентов»,
   а из ЖЕЛАЕМОГО ТЕМПА изменения веса: 1 кг жировой ткани ~ 7700 ккал,
   поэтому темп 0.5 кг/нед = 0.5 x 7700 / 7 ~ 550 ккал/сутки дефицита.
   Такой подход даёт честный прогноз сроков, чего проценты не дают.
4. Ограничители безопасности (в порядке применения):
   - темп похудения не быстрее 1% массы тела в неделю (риск потери мышц);
   - дефицит не более 25% от TDEE, профицит не более 20%;
   - калорийность не ниже BMR (нельзя есть меньше базового обмена вдолгую);
   - абсолютный пол: 1500 ккал мужчины / 1200 ккал женщины.
   Каждое срабатывание возвращается в warnings — фронт может объяснить
   пользователю, почему выбранный им темп был скорректирован.
5. БЖУ считаются НЕ процентами от калорий, а «снизу вверх»:
   - белок — г на кг референсной массы (защищает мышцы в дефиците);
   - жир — г на кг, не ниже гормонального минимума;
   - углеводы — остаток калорий (топливо, самый гибкий макрос).
   Проценты от калорий при 1300 ккал дают ~97 г белка, а при 3500 ккал —
   ~260 г: первое мало, второе бессмысленно много. Привязка к массе тела
   такого перекоса не даёт.

Референсная масса для БЖУ
-------------------------
При ожирении (ИМТ > 30) грамм-на-килограмм от фактического веса завышает
норму белка: жировая ткань метаболически малоактивна. Поэтому берём
скорректированную массу ABW = W25 + 0.25 x (факт - W25), где W25 — вес при
ИМТ 25. Это клинический приём (adjusted body weight) в адаптации под ИМТ.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Dict, List, Literal, Optional

# ==================== СЛОВАРИ И КОНСТАНТЫ ====================

Goal = Literal["lose", "maintain", "gain"]

GOALS: tuple[str, ...] = ("lose", "maintain", "gain")
DEFAULT_GOAL: str = "maintain"

ACTIVITY_LEVELS: tuple[str, ...] = (
    "sedentary", "light", "moderate", "active", "very_active",
)
DEFAULT_ACTIVITY: str = "sedentary"

# Коэффициенты физической активности (множитель к BMR -> TDEE).
ACTIVITY_FACTORS: Dict[str, float] = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

# Калорийность 1 г макронутриента.
KCAL_PER_GRAM: Dict[str, float] = {"protein": 4.0, "fat": 9.0, "carbs": 4.0}

# Энергетический эквивалент 1 кг изменения массы тела.
# Похудение: 1 кг жировой ткани ~ 7700 ккал (классическая оценка Wishnofsky).
KCAL_PER_KG_LOSS = 7700.0
# Набор: прибавка — смесь мышц (энергетически «дешёвых», много воды) и жира,
# поэтому 1 кг обходится дешевле. 6000 ккал/кг — рабочая оценка для смешанной
# ткани при умеренном профиците.
KCAL_PER_KG_GAIN = 6000.0

# --- Пресеты темпа (кг/нед). Фронт показывает их как «мягкий/умеренный/
# агрессивный», но в БД хранится само число: пользователь может задать своё. ---
RATE_PRESETS: Dict[str, Dict[str, float]] = {
    "lose": {"gentle": 0.25, "moderate": 0.5, "aggressive": 0.75},
    "gain": {"gentle": 0.125, "moderate": 0.25, "aggressive": 0.5},
    "maintain": {"gentle": 0.0, "moderate": 0.0, "aggressive": 0.0},
}
DEFAULT_RATE: Dict[str, float] = {"lose": 0.5, "gain": 0.25, "maintain": 0.0}

# Верхняя граница вводимого темпа (валидация схемы), кг/нед.
MAX_INPUT_RATE_KG_PER_WEEK = 1.5

# --- Ограничители безопасности ---
# Максимальный темп похудения как доля массы тела в неделю.
MAX_LOSS_RATE_BODY_FRACTION = 0.01
# Максимальный темп набора как доля массы тела в неделю (быстрее — «в жир»).
MAX_GAIN_RATE_BODY_FRACTION = 0.005
# Максимальные дефицит/профицит относительно TDEE.
MAX_DEFICIT_FRACTION = 0.25
MAX_SURPLUS_FRACTION = 0.20
# Абсолютный минимум суточной калорийности (ккал) по полу.
MIN_CALORIES_BY_SEX: Dict[str, int] = {"male": 1500, "female": 1200}
MIN_CALORIES_FALLBACK = 1200

# --- Референсная масса для БЖУ ---
OBESITY_BMI = 30.0            # порог, с которого используем скорр. массу
REFERENCE_BMI = 25.0          # «нормальный» ИМТ для расчёта W25
EXCESS_WEIGHT_SHARE = 0.25    # какую долю избытка учитываем в норме БЖУ

# --- Белок, г/кг референсной массы ---
# В дефиците белок выше: он сохраняет мышцы и лучше насыщает. При наборе —
# строительный материал. При поддержании достаточно умеренной нормы.
PROTEIN_G_PER_KG_BY_GOAL: Dict[str, float] = {
    "lose": 1.8, "maintain": 1.4, "gain": 1.8,
}
# Надбавка за тренировочный объём (мышцы «просят» больше белка).
PROTEIN_G_PER_KG_ACTIVITY_BONUS: Dict[str, float] = {
    "sedentary": -0.2, "light": 0.0, "moderate": 0.1,
    "active": 0.2, "very_active": 0.3,
}
PROTEIN_G_PER_KG_MIN = 1.2
PROTEIN_G_PER_KG_MAX = 2.4

# --- Жир, г/кг референсной массы ---
# 0.8 г/кг — принятый нижний порог для гормонального здоровья; ниже опускаться
# нельзя даже в жёстком дефиците.
FAT_G_PER_KG_BY_GOAL: Dict[str, float] = {
    "lose": 0.9, "maintain": 1.0, "gain": 1.0,
}
FAT_G_PER_KG_FLOOR = 0.8
# Коридор доли жира в калорийности — страховка для крайних случаев
# (очень низкая калорийность / очень большая масса).
FAT_KCAL_SHARE_MIN = 0.20
FAT_KCAL_SHARE_MAX = 0.40

# Минимум углеводов (г/сут): ЦНС потребляет ~100-130 г глюкозы в сутки.
CARBS_G_MIN = 100.0

# --- Вода ---
GLASS_ML = 250  # объём одного стакана — единица учёта в трекере

# Норма воды считается как «мл на кг массы тела»: базовая медицинская норма
# ~30 мл/кг, с ростом активности потребность выше.
WATER_ML_PER_KG: Dict[str, int] = {
    "sedentary": 30, "light": 32, "moderate": 35, "active": 38, "very_active": 40,
}
# Похудение повышает потребность в воде (выведение продуктов липолиза,
# больше белка в рационе -> выше азотистая нагрузка на почки).
WATER_GOAL_BONUS_ML_PER_KG: Dict[str, int] = {"lose": 2, "maintain": 0, "gain": 1}

# Цель считается достигнутой, если до целевого веса осталось меньше, чем это
# (кг): колебания воды в теле легко дают +-0.5 кг, гнаться за ними бессмысленно.
GOAL_REACHED_TOLERANCE_KG = 0.5

# Коды предупреждений (стабильные, фронт может локализовать по коду).
W_RATE_CAPPED = "rate_capped"
W_DEFICIT_CAPPED = "deficit_capped"
W_SURPLUS_CAPPED = "surplus_capped"
W_BELOW_BMR = "below_bmr"
W_ABSOLUTE_FLOOR = "absolute_floor"
W_TARGET_CONFLICTS_GOAL = "target_conflicts_goal"
W_GOAL_REACHED = "goal_reached"
W_MISSING_DATA = "missing_data"


# ==================== РЕЗУЛЬТАТ ====================

@dataclass
class GoalPlan:
    """Как цель превратилась в суточную поправку калорий (для UI и советчика)."""
    goal: str
    # Запрошенный пользователем темп и фактически применённый после
    # ограничителей — расходятся, если темп был слишком агрессивным.
    requested_rate_kg_per_week: float
    applied_rate_kg_per_week: float
    target_weight_kg: Optional[float] = None
    # Суточная поправка к TDEE: отрицательная = дефицит, положительная = профицит.
    calorie_delta: float = 0.0
    # Доля поправки от TDEE, % (для подписи «дефицит 18%»).
    calorie_delta_pct: Optional[float] = None
    # Прогноз: сколько осталось и когда цель будет достигнута.
    remaining_kg: Optional[float] = None
    weeks_to_goal: Optional[float] = None
    eta_date: Optional[date] = None
    reached: bool = False

    def as_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "requested_rate_kg_per_week": self.requested_rate_kg_per_week,
            "applied_rate_kg_per_week": self.applied_rate_kg_per_week,
            "target_weight_kg": self.target_weight_kg,
            "calorie_delta": self.calorie_delta,
            "calorie_delta_pct": self.calorie_delta_pct,
            "remaining_kg": self.remaining_kg,
            "weeks_to_goal": self.weeks_to_goal,
            "eta_date": self.eta_date,
            "reached": self.reached,
        }


@dataclass
class NutritionPlan:
    """Полный расчёт суточных норм. None в полях = не хватило исходных данных."""
    bmr: Optional[float] = None
    tdee: Optional[float] = None
    calories: Optional[float] = None
    protein_g: Optional[float] = None
    fat_g: Optional[float] = None
    carbs_g: Optional[float] = None
    water_ml: Optional[float] = None
    bmi: Optional[float] = None
    reference_weight_kg: Optional[float] = None
    goal_plan: Optional[GoalPlan] = None
    warnings: List[Dict[str, str]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "bmr": self.bmr,
            "tdee": self.tdee,
            "calories": self.calories,
            "protein_g": self.protein_g,
            "fat_g": self.fat_g,
            "carbs_g": self.carbs_g,
            "water_ml": self.water_ml,
            "bmi": self.bmi,
            "reference_weight_kg": self.reference_weight_kg,
            "goal_plan": self.goal_plan.as_dict() if self.goal_plan else None,
            "warnings": list(self.warnings),
        }


# ==================== ШАГ 0: ВСПОМОГАТЕЛЬНОЕ ====================

def calc_age(birth_date: Optional[date], today: Optional[date] = None) -> Optional[int]:
    """Полных лет на дату (по умолчанию — сегодня)."""
    if not birth_date:
        return None
    today = today or date.today()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def normalize_goal(goal: Optional[str]) -> str:
    return goal if goal in GOALS else DEFAULT_GOAL


def normalize_activity(activity_level: Optional[str]) -> str:
    return activity_level if activity_level in ACTIVITY_LEVELS else DEFAULT_ACTIVITY


def calc_bmi(weight_kg: Optional[float], height_cm: Optional[float]) -> Optional[float]:
    """Индекс массы тела. None, если нет веса или роста."""
    if not weight_kg or not height_cm:
        return None
    height_m = height_cm / 100.0
    return round(weight_kg / (height_m * height_m), 1)


def _warn(code: str, message: str) -> Dict[str, str]:
    return {"code": code, "message": message}


# ==================== ШАГ 1-2: BMR И TDEE ====================

def calc_bmr(weight_kg: Optional[float], height_cm: Optional[float],
             age: Optional[int], sex: Optional[str]) -> Optional[float]:
    """Базовый обмен веществ по формуле Миффлина–Сан-Жеора.
    Возвращает None, если данных не хватает."""
    if not weight_kg or not height_cm or age is None or not sex:
        return None
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    return round(base + (5 if sex == "male" else -161), 1)


def calc_tdee(bmr: Optional[float], activity_level: Optional[str]) -> Optional[float]:
    """Суточный расход при текущей активности (норма поддержания веса)."""
    if bmr is None:
        return None
    return round(bmr * ACTIVITY_FACTORS[normalize_activity(activity_level)])


# ==================== ШАГ 3-4: ЦЕЛЬ -> КАЛОРИИ ====================

def resolve_rate(goal: str, rate_kg_per_week: Optional[float]) -> float:
    """Желаемый темп изменения веса, кг/нед (всегда >= 0, знак задаёт цель)."""
    if goal == "maintain":
        return 0.0
    if rate_kg_per_week is None:
        return DEFAULT_RATE[goal]
    return min(abs(float(rate_kg_per_week)), MAX_INPUT_RATE_KG_PER_WEEK)


def _cap_rate_by_body_weight(goal: str, rate: float, weight_kg: Optional[float],
                             warnings: List[Dict[str, str]]) -> float:
    """Ограничитель 1: темп не быстрее X% массы тела в неделю."""
    if goal == "maintain" or not weight_kg or rate <= 0:
        return rate
    fraction = (
        MAX_LOSS_RATE_BODY_FRACTION if goal == "lose" else MAX_GAIN_RATE_BODY_FRACTION
    )
    max_rate = round(weight_kg * fraction, 3)
    if rate <= max_rate:
        return rate
    warnings.append(_warn(
        W_RATE_CAPPED,
        f"Темп снижен до {max_rate} кг/нед — это безопасный максимум "
        f"({fraction * 100:g}% массы тела в неделю) для вашего веса.",
    ))
    return max_rate


def _rate_to_delta(goal: str, rate: float) -> float:
    """Темп (кг/нед) -> суточная поправка калорий (знак: - дефицит, + профицит)."""
    if goal == "maintain" or rate <= 0:
        return 0.0
    kcal_per_kg = KCAL_PER_KG_LOSS if goal == "lose" else KCAL_PER_KG_GAIN
    delta = rate * kcal_per_kg / 7.0
    return -delta if goal == "lose" else delta


def _delta_to_rate(goal: str, delta: float) -> float:
    """Обратное преобразование: сколько кг/нед даёт такая поправка калорий."""
    if goal == "maintain" or delta == 0:
        return 0.0
    kcal_per_kg = KCAL_PER_KG_LOSS if goal == "lose" else KCAL_PER_KG_GAIN
    return round(abs(delta) * 7.0 / kcal_per_kg, 3)


def apply_calorie_guardrails(tdee: float, delta: float, bmr: Optional[float],
                             sex: Optional[str],
                             warnings: List[Dict[str, str]]) -> float:
    """Ограничители 2-4: относительный коридор, пол BMR и абсолютный минимум.
    Возвращает итоговую калорийность (уже с учётом поправки)."""
    # 2. Относительный коридор от TDEE
    if delta < 0 and abs(delta) > tdee * MAX_DEFICIT_FRACTION:
        delta = -tdee * MAX_DEFICIT_FRACTION
        warnings.append(_warn(
            W_DEFICIT_CAPPED,
            f"Дефицит ограничен {MAX_DEFICIT_FRACTION:.0%} от суточного расхода — "
            "более резкий приводит к потере мышц и срывам.",
        ))
    elif delta > 0 and delta > tdee * MAX_SURPLUS_FRACTION:
        delta = tdee * MAX_SURPLUS_FRACTION
        warnings.append(_warn(
            W_SURPLUS_CAPPED,
            f"Профицит ограничен {MAX_SURPLUS_FRACTION:.0%} от суточного расхода — "
            "избыток сверх этого уходит преимущественно в жир.",
        ))

    calories = tdee + delta

    # 3. Не ниже базового обмена
    if bmr is not None and calories < bmr:
        calories = bmr
        warnings.append(_warn(
            W_BELOW_BMR,
            "Норма поднята до уровня базового обмена: питаться ниже него "
            "длительно небезопасно.",
        ))

    # 4. Абсолютный пол по полу
    floor = MIN_CALORIES_BY_SEX.get(sex or "", MIN_CALORIES_FALLBACK)
    if calories < floor:
        calories = float(floor)
        warnings.append(_warn(
            W_ABSOLUTE_FLOOR,
            f"Норма поднята до минимальных {floor} ккал — ниже этого рацион "
            "не покрывает потребность в витаминах и минералах.",
        ))

    return calories


def build_goal_plan(
    goal: Optional[str],
    weight_kg: Optional[float],
    tdee: Optional[float],
    bmr: Optional[float],
    sex: Optional[str],
    rate_kg_per_week: Optional[float] = None,
    target_weight_kg: Optional[float] = None,
    today: Optional[date] = None,
) -> tuple[GoalPlan, Optional[float], List[Dict[str, str]]]:
    """Цель -> (план цели, суточная норма калорий, предупреждения)."""
    today = today or date.today()
    goal = normalize_goal(goal)
    warnings: List[Dict[str, str]] = []
    requested_rate = resolve_rate(goal, rate_kg_per_week)

    # --- Согласование цели и целевого веса ---
    remaining_kg: Optional[float] = None
    if target_weight_kg and weight_kg:
        delta_kg = target_weight_kg - weight_kg  # + нужно набрать, - нужно сбросить
        if abs(delta_kg) < GOAL_REACHED_TOLERANCE_KG:
            # Целевой вес достигнут -> переходим в поддержание, но цель не
            # затираем: пользователь сам решит, менять её или нет.
            warnings.append(_warn(
                W_GOAL_REACHED,
                "Целевой вес достигнут — норма рассчитана на поддержание.",
            ))
            goal_effective = "maintain"
            requested_rate = 0.0
            remaining_kg = 0.0
        else:
            wants = "gain" if delta_kg > 0 else "lose"
            if goal != "maintain" and goal != wants:
                warnings.append(_warn(
                    W_TARGET_CONFLICTS_GOAL,
                    "Целевой вес не согласуется с выбранной целью — "
                    "прогноз сроков не строится.",
                ))
                target_weight_kg = None
                goal_effective = goal
            else:
                goal_effective = goal
                remaining_kg = round(abs(delta_kg), 1)
    else:
        goal_effective = goal

    if tdee is None:
        # Данных на калории не хватает — отдаём «скелет» плана без цифр.
        plan = GoalPlan(
            goal=goal,
            requested_rate_kg_per_week=requested_rate,
            applied_rate_kg_per_week=requested_rate,
            target_weight_kg=target_weight_kg,
            remaining_kg=remaining_kg,
            reached=remaining_kg == 0.0,
        )
        return plan, None, warnings

    # --- Темп -> поправка -> ограничители ---
    applied_rate = _cap_rate_by_body_weight(
        goal_effective, requested_rate, weight_kg, warnings
    )
    delta = _rate_to_delta(goal_effective, applied_rate)
    calories = apply_calorie_guardrails(tdee, delta, bmr, sex, warnings)

    # Фактическая поправка после всех ограничителей — из неё и считаем прогноз,
    # чтобы обещанные сроки соответствовали выданной норме калорий.
    effective_delta = round(calories - tdee)
    effective_rate = _delta_to_rate(goal_effective, effective_delta)

    weeks_to_goal: Optional[float] = None
    eta: Optional[date] = None
    if remaining_kg and effective_rate > 0:
        weeks_to_goal = round(remaining_kg / effective_rate, 1)
        eta = today + timedelta(weeks=weeks_to_goal)

    plan = GoalPlan(
        goal=goal,
        requested_rate_kg_per_week=requested_rate,
        applied_rate_kg_per_week=effective_rate,
        target_weight_kg=target_weight_kg,
        calorie_delta=effective_delta,
        calorie_delta_pct=round(effective_delta / tdee * 100, 1) if tdee else None,
        remaining_kg=remaining_kg,
        weeks_to_goal=weeks_to_goal,
        eta_date=eta,
        reached=remaining_kg == 0.0,
    )
    return plan, round(calories), warnings


# ==================== ШАГ 5: БЖУ ====================

def reference_weight_for_macros(weight_kg: Optional[float],
                                height_cm: Optional[float]) -> Optional[float]:
    """Масса, от которой считаются граммы белка/жира.

    При ИМТ <= 30 это фактический вес. Выше — скорректированная масса:
    вес при ИМТ 25 плюс четверть избытка. Иначе норма белка для человека
    со 140 кг получилась бы нереалистичной (~250 г)."""
    if not weight_kg:
        return None
    bmi = calc_bmi(weight_kg, height_cm)
    if bmi is None or bmi <= OBESITY_BMI:
        return round(weight_kg, 1)
    height_m = height_cm / 100.0
    normal_weight = REFERENCE_BMI * height_m * height_m
    adjusted = normal_weight + EXCESS_WEIGHT_SHARE * (weight_kg - normal_weight)
    return round(adjusted, 1)


def protein_g_per_kg(goal: str, activity_level: Optional[str]) -> float:
    """Норма белка в г/кг референсной массы: база по цели + надбавка за объём."""
    base = PROTEIN_G_PER_KG_BY_GOAL[normalize_goal(goal)]
    bonus = PROTEIN_G_PER_KG_ACTIVITY_BONUS[normalize_activity(activity_level)]
    return round(min(max(base + bonus, PROTEIN_G_PER_KG_MIN), PROTEIN_G_PER_KG_MAX), 2)


def calc_macro_targets(
    calories: Optional[float],
    weight_kg: Optional[float] = None,
    height_cm: Optional[float] = None,
    goal: Optional[str] = None,
    activity_level: Optional[str] = None,
) -> Dict[str, Optional[float]]:
    """Нормы БЖУ (граммы) под цель.

    Порядок: белок (г/кг) -> жир (г/кг, с коридором доли калорий) -> углеводы
    остатком. Если остатка не хватает, ужимаем сначала жир (до 0.8 г/кг),
    затем белок — но не ниже нижних физиологических границ."""
    if not calories:
        return {"protein_g": None, "fat_g": None, "carbs_g": None}

    ref_weight = reference_weight_for_macros(weight_kg, height_cm)
    if ref_weight is None:
        # Веса нет — единственный доступный вариант это проценты от калорий.
        # Пропорция сбалансированная: 25/30/45.
        return {
            "protein_g": round(calories * 0.25 / KCAL_PER_GRAM["protein"]),
            "fat_g": round(calories * 0.30 / KCAL_PER_GRAM["fat"]),
            "carbs_g": round(calories * 0.45 / KCAL_PER_GRAM["carbs"]),
        }

    goal = normalize_goal(goal)

    # --- Белок ---
    protein_g = ref_weight * protein_g_per_kg(goal, activity_level)

    # --- Жир: г/кг, но с коридором доли калорий ---
    fat_g = ref_weight * FAT_G_PER_KG_BY_GOAL[goal]
    fat_min_g = max(
        ref_weight * FAT_G_PER_KG_FLOOR,
        calories * FAT_KCAL_SHARE_MIN / KCAL_PER_GRAM["fat"],
    )
    fat_max_g = calories * FAT_KCAL_SHARE_MAX / KCAL_PER_GRAM["fat"]
    fat_g = min(max(fat_g, fat_min_g), max(fat_max_g, fat_min_g))

    # --- Углеводы: остаток ---
    def carbs_from(p: float, f: float) -> float:
        used = p * KCAL_PER_GRAM["protein"] + f * KCAL_PER_GRAM["fat"]
        return (calories - used) / KCAL_PER_GRAM["carbs"]

    carbs_g = carbs_from(protein_g, fat_g)

    # Остатка не хватило (низкая калорийность при большой массе): ужимаем жир
    # до физиологического минимума, затем белок — но не ниже 1.2 г/кг.
    if carbs_g < CARBS_G_MIN:
        fat_floor = ref_weight * FAT_G_PER_KG_FLOOR
        if fat_g > fat_floor:
            fat_g = max(fat_floor, fat_g - (CARBS_G_MIN - carbs_g)
                        * KCAL_PER_GRAM["carbs"] / KCAL_PER_GRAM["fat"])
            carbs_g = carbs_from(protein_g, fat_g)
    if carbs_g < CARBS_G_MIN:
        protein_floor = ref_weight * PROTEIN_G_PER_KG_MIN
        if protein_g > protein_floor:
            protein_g = max(protein_floor, protein_g - (CARBS_G_MIN - carbs_g))
            carbs_g = carbs_from(protein_g, fat_g)

    return {
        "protein_g": round(protein_g),
        "fat_g": round(fat_g),
        "carbs_g": round(max(carbs_g, 0)),
    }


# ==================== ВОДА ====================

def calc_water_target(weight_kg: Optional[float],
                      activity_level: Optional[str] = None,
                      goal: Optional[str] = None) -> Optional[float]:
    """Суточная норма воды (мл) = вес x (мл/кг по активности и цели).
    Рост и возраст на питьевую норму напрямую не влияют — определяющие
    факторы это масса тела, активность и режим питания."""
    if not weight_kg:
        return None
    ml_per_kg = WATER_ML_PER_KG[normalize_activity(activity_level)]
    ml_per_kg += WATER_GOAL_BONUS_ML_PER_KG[normalize_goal(goal)]
    return round(weight_kg * ml_per_kg)


# ==================== ГЛАВНАЯ ТОЧКА ВХОДА ====================

def build_plan(
    weight_kg: Optional[float],
    height_cm: Optional[float],
    age: Optional[int],
    sex: Optional[str],
    activity_level: Optional[str] = None,
    goal: Optional[str] = None,
    goal_rate_kg_per_week: Optional[float] = None,
    target_weight_kg: Optional[float] = None,
    today: Optional[date] = None,
) -> NutritionPlan:
    """Полный расчёт норм под цель. Единственная функция, которую нужно
    вызывать снаружи — остальные экспортированы для тестов и переиспользования."""
    goal = normalize_goal(goal)
    bmr = calc_bmr(weight_kg, height_cm, age, sex)
    tdee = calc_tdee(bmr, activity_level)

    goal_plan, calories, warnings = build_goal_plan(
        goal=goal,
        weight_kg=weight_kg,
        tdee=tdee,
        bmr=bmr,
        sex=sex,
        rate_kg_per_week=goal_rate_kg_per_week,
        target_weight_kg=target_weight_kg,
        today=today,
    )

    if calories is None:
        missing = [
            name for name, value in (
                ("вес", weight_kg), ("рост", height_cm),
                ("возраст", age), ("пол", sex),
            ) if not value
        ]
        warnings.append(_warn(
            W_MISSING_DATA,
            "Не хватает данных для расчёта норм: " + ", ".join(missing) + ".",
        ))

    macros = calc_macro_targets(
        calories, weight_kg=weight_kg, height_cm=height_cm,
        goal=goal_plan.goal if goal_plan else goal, activity_level=activity_level,
    )

    return NutritionPlan(
        bmr=bmr,
        tdee=tdee,
        calories=calories,
        protein_g=macros["protein_g"],
        fat_g=macros["fat_g"],
        carbs_g=macros["carbs_g"],
        water_ml=calc_water_target(weight_kg, activity_level, goal),
        bmi=calc_bmi(weight_kg, height_cm),
        reference_weight_kg=reference_weight_for_macros(weight_kg, height_cm),
        goal_plan=goal_plan,
        warnings=warnings,
    )
