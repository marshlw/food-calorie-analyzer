"""Правила «Целей» — геймификация дневника (вкладка «Приёмы» → «Путь»).

Чистый модуль без зависимостей от БД и FastAPI: на вход — фактические цифры
дня (сколько приёмов записано, сколько выпито воды, сколько белка) и нормы
пользователя, на выходе — цели дня, статус дня, искры и серия. Так правила
тестируются юнит-тестами и переиспользуются из crud / бота / советчика —
ровно по той же схеме, что и app/nutrition.py.

Модель (по шагам)
-----------------
1. ЦЕЛЬ ДНЯ — три задачи, которые закрываются АВТОМАТИЧЕСКИ по фактическим
   записям пользователя, а не «галочкой». Ручной чекбокс обесценивает серию:
   отметить можно и не поев.
     - meals   — записать приёмы пищи (>= MEALS_TARGET записей);
     - water   — выполнить норму воды;
     - protein — набрать белок (>= PROTEIN_DONE_RATIO от нормы).
   Если нормы у пользователя нет (пустой профиль), соответствующая цель
   считается недоступной (target=None) и в знаменатель не идёт — иначе
   новичок без профиля никогда не закрыл бы день.
2. ИСКРЫ (sparks) — очки за выполненные цели, см. GOAL_SPARKS. Валюта
   прогресса: показываются в тосте «День закрыт — N искр».
3. СТАТУС ДНЯ:
     - closed  — выполнены ВСЕ доступные цели дня (день закрыт);
     - partial — выполнена хотя бы одна, но не все;
     - frozen  — день спасён «заморозкой» (см. ниже);
     - missed  — не выполнено ничего;
     - future  — день ещё не наступил.
4. СЕРИЯ (streak) — сколько дней подряд, считая назад от сегодня, день
   закрыт или заморожен. Сегодняшний незакрытый день серию НЕ обрывает
   (день ещё идёт), а вот вчерашний пропуск — обрывает.
5. ЗАМОРОЗКА — расходуемый «щит»: день без записей засчитывается как
   сохранённый и серия не обрывается. Заморозки начисляются за вехи
   (см. REWARDS) и тратятся вручную.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Iterable, List, Literal, Mapping, Optional

# ==================== КОНСТАНТЫ ПРАВИЛ ====================

DayStatus = Literal["closed", "partial", "frozen", "missed", "future"]

STATUS_CLOSED: str = "closed"
STATUS_PARTIAL: str = "partial"
STATUS_FROZEN: str = "frozen"
STATUS_MISSED: str = "missed"
STATUS_FUTURE: str = "future"

# Статусы, которые продлевают серию.
STREAK_STATUSES: frozenset = frozenset({STATUS_CLOSED, STATUS_FROZEN})

# Идентификаторы целей дня — стабильные ключи для фронта и БД.
GOAL_MEALS: str = "meals"
GOAL_WATER: str = "water"
GOAL_PROTEIN: str = "protein"
GOAL_IDS: tuple[str, ...] = (GOAL_MEALS, GOAL_WATER, GOAL_PROTEIN)

# Сколько приёмов пищи нужно записать, чтобы цель «meals» закрылась.
MEALS_TARGET: int = 3

# Доля нормы, с которой цель считается выполненной. Требовать 100% белка
# и воды день в день — верный способ обесценить серию: колебания в 2–3%
# неизбежны, а мотивация ломается. 90% — достижимый честный порог.
PROTEIN_DONE_RATIO: float = 0.9
WATER_DONE_RATIO: float = 0.9

# Искры за выполненную цель.
GOAL_SPARKS: Dict[str, int] = {
    GOAL_MEALS: 10,
    GOAL_WATER: 3,
    GOAL_PROTEIN: 3,
}

# Подписи целей для UI (бэкенд отдаёт готовый текст — фронт не дублирует
# правила и не разъезжается с ними при смене порогов).
GOAL_LABELS: Dict[str, str] = {
    GOAL_MEALS: "Записать приёмы пищи",
    GOAL_WATER: "Норма воды",
    GOAL_PROTEIN: "Белок по цели",
}

# Вехи «Пути месяца»: длина серии -> короткая подпись под кружком.
MILESTONES: Dict[int, str] = {
    7: "7 дней",
    14: "2 недели",
    21: "3 недели",
    30: "месяц",
}

# Сколько заморозок у нового пользователя.
DEFAULT_FREEZES: int = 2

# Максимальный «возраст» дня, который ещё можно заморозить (дней назад).
# Иначе заморозка превращается в машину времени и обесценивает серию.
FREEZE_MAX_AGE_DAYS: int = 7


@dataclass(frozen=True)
class RewardRule:
    """Награда за длину серии. bonus_freezes начисляются один раз — в тот
    день, когда серия впервые достигла threshold (см. crud.grant_rewards)."""

    code: str
    threshold: int
    title: str
    subtitle: str
    # Короткое имя для подсказки «до награды «2 недели» — 5 дней».
    short: str
    bonus_freezes: int = 0


REWARDS: tuple[RewardRule, ...] = (
    RewardRule("week", 7, "Неделя без пропусков", "Открыт бейдж «Ритм»", "неделя"),
    RewardRule(
        "two_weeks", 14, "Две недели подряд", "Открыта заморозка +1", "2 недели",
        bonus_freezes=1,
    ),
    RewardRule(
        "month", 30, "Месяц дисциплины", "Открыта заморозка +1", "месяц",
        bonus_freezes=1,
    ),
)


# ==================== ТЕКСТОВЫЕ ХЕЛПЕРЫ ====================

def plural(n: int, one: str, few: str, many: str) -> str:
    """Русское склонение числительных: 1 день, 2 дня, 5 дней."""
    n = abs(int(n))
    m10, m100 = n % 10, n % 100
    if m10 == 1 and m100 != 11:
        return one
    if 2 <= m10 <= 4 and not (12 <= m100 <= 14):
        return few
    return many


def days_word(n: int) -> str:
    return plural(n, "день", "дня", "дней")


def _fmt_number(value: float) -> str:
    """1400.0 -> «1400», 1.4 -> «1,4» (русская запятая)."""
    rounded = round(float(value), 1)
    if abs(rounded - round(rounded)) < 0.05:
        return str(int(round(rounded)))
    return f"{rounded:.1f}".replace(".", ",")


# ==================== ЦЕЛИ ДНЯ ====================

@dataclass
class DailyGoal:
    """Одна цель дня в готовом для UI виде."""

    id: str
    label: str
    hint: str
    reward: int
    done: bool
    # current/target — сырые цифры для прогресс-баров. target=None означает
    # «норма не задана» (пустой профиль): цель показывается, но не блокирует
    # закрытие дня.
    current: float
    target: Optional[float]
    unit: str

    @property
    def available(self) -> bool:
        return self.target is not None and self.target > 0

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "hint": self.hint,
            "reward": self.reward,
            "done": self.done,
            "current": round(self.current, 1),
            "target": round(self.target, 1) if self.target is not None else None,
            "unit": self.unit,
            "available": self.available,
        }


def build_daily_goals(
    *,
    meals_count: int,
    water_ml: float,
    water_target_ml: Optional[float],
    protein_g: float,
    protein_target_g: Optional[float],
) -> List[DailyGoal]:
    """Три цели дня по фактическим цифрам. Порядок фиксирован — он же
    порядок отображения в карточке «Цель дня»."""
    meals_done = meals_count >= MEALS_TARGET
    meals = DailyGoal(
        id=GOAL_MEALS,
        label=GOAL_LABELS[GOAL_MEALS],
        hint=(
            f"{meals_count} из {MEALS_TARGET} — так держать"
            if meals_done
            else f"{meals_count} из {MEALS_TARGET} — добавьте ещё "
                 f"{MEALS_TARGET - meals_count} {plural(MEALS_TARGET - meals_count, 'приём', 'приёма', 'приёмов')}"
        ),
        reward=GOAL_SPARKS[GOAL_MEALS],
        done=meals_done,
        current=float(meals_count),
        target=float(MEALS_TARGET),
        unit="приём",
    )

    water_done = bool(
        water_target_ml and water_ml >= water_target_ml * WATER_DONE_RATIO
    )
    water_hint = (
        f"{_fmt_number(water_ml / 1000)} из {_fmt_number(water_target_ml / 1000)} л"
        if water_target_ml
        else f"{_fmt_number(water_ml / 1000)} л — задайте вес в профиле"
    )
    water = DailyGoal(
        id=GOAL_WATER,
        label=GOAL_LABELS[GOAL_WATER],
        hint=water_hint,
        reward=GOAL_SPARKS[GOAL_WATER],
        done=water_done,
        current=float(water_ml),
        target=float(water_target_ml) if water_target_ml else None,
        unit="мл",
    )

    protein_done = bool(
        protein_target_g and protein_g >= protein_target_g * PROTEIN_DONE_RATIO
    )
    protein_hint = (
        f"{_fmt_number(protein_g)} из {_fmt_number(protein_target_g)} г"
        if protein_target_g
        else f"{_fmt_number(protein_g)} г — норма не задана"
    )
    protein = DailyGoal(
        id=GOAL_PROTEIN,
        label=GOAL_LABELS[GOAL_PROTEIN],
        hint=protein_hint,
        reward=GOAL_SPARKS[GOAL_PROTEIN],
        done=protein_done,
        current=float(protein_g),
        target=float(protein_target_g) if protein_target_g else None,
        unit="г",
    )

    return [meals, water, protein]


def count_sparks(goals: Iterable[DailyGoal]) -> int:
    return sum(g.reward for g in goals if g.done)


def resolve_status(
    goals: List[DailyGoal],
    *,
    frozen: bool = False,
    day: Optional[date] = None,
    today: Optional[date] = None,
) -> str:
    """Статус дня по его целям. frozen имеет приоритет: заморозка — это
    явное действие пользователя, её не должен перебивать пересчёт."""
    today = today or date.today()
    if day is not None and day > today:
        return STATUS_FUTURE
    if frozen:
        return STATUS_FROZEN

    available = [g for g in goals if g.available]
    done = [g for g in available if g.done]
    if available and len(done) == len(available):
        return STATUS_CLOSED
    if done:
        return STATUS_PARTIAL
    return STATUS_MISSED


def is_closed(status: str) -> bool:
    return status == STATUS_CLOSED


# ==================== СЕРИЯ ====================

def compute_streak(statuses: Mapping[date, str], today: date) -> int:
    """Длина серии на сегодня.

    Идём назад от сегодняшнего дня. Сегодня — особый случай: день ещё не
    закончился, поэтому незакрытое «сегодня» серию не обрывает, а просто
    не увеличивает. Любой другой незакрытый день обрывает.
    """
    streak = 1 if statuses.get(today) in STREAK_STATUSES else 0
    cursor = today - timedelta(days=1)

    while statuses.get(cursor) in STREAK_STATUSES:
        streak += 1
        cursor -= timedelta(days=1)

    return streak


def compute_best_streak(statuses: Mapping[date, str]) -> int:
    """Рекорд по всей истории статусов (для «Рекорд N» на карточке)."""
    if not statuses:
        return 0
    best = 0
    run = 0
    previous: Optional[date] = None
    for day in sorted(statuses):
        if previous is not None and (day - previous).days > 1:
            run = 0  # разрыв в данных = дни без записей = пропуск
        run = run + 1 if statuses[day] in STREAK_STATUSES else 0
        best = max(best, run)
        previous = day
    return best


# ==================== ТЕКСТЫ И НАГРАДЫ ====================

def streak_title(streak: int) -> str:
    return f"{streak} {days_word(streak)} подряд"


def streak_hint(*, day_closed: bool, goals_left: int) -> str:
    if day_closed:
        return "Сегодня отмечено — так держать"
    if goals_left <= 0:
        return "День ещё не закрыт"
    return f"День не закрыт — осталось {goals_left} {plural(goals_left, 'цель', 'цели', 'целей')}"


def next_reward_hint(streak: int) -> str:
    """Подсказка «до следующей награды». None-состояния нет: после последней
    вехи показываем поздравление, а не пустую строку."""
    for rule in REWARDS:
        if streak < rule.threshold:
            left = rule.threshold - streak
            return f"До награды «{rule.short}» — {left} {days_word(left)}"
    return "Все награды открыты — вы держите ритм"


def build_rewards(streak: int, best_streak: int) -> List[dict]:
    """Список наград для UI. Награда «достигнута», если её порог когда-либо
    был взят (рекорд), — сорванная серия не должна отнимать бейдж."""
    reference = max(streak, best_streak)
    out: List[dict] = []
    for rule in REWARDS:
        reached = reference >= rule.threshold
        if reached:
            subtitle = rule.subtitle
        else:
            left = rule.threshold - streak
            subtitle = f"Ещё {left} {days_word(left)}"
        out.append(
            {
                "code": rule.code,
                "threshold": rule.threshold,
                "title": rule.title,
                "subtitle": subtitle,
                "mark": str(rule.threshold),
                "reached": reached,
            }
        )
    return out


def milestone_for(streak_position: int) -> Optional[str]:
    """Подпись вехи для кружка «Пути месяца». streak_position — длина серии
    на этот день (а не номер дня в месяце): веха «7 дней» должна стоять на
    седьмом дне СЕРИИ, иначе она не значит ничего."""
    return MILESTONES.get(streak_position)


def can_freeze(day: date, today: date, status: str, freezes_available: int) -> Optional[str]:
    """Проверка возможности заморозить день. Возвращает текст ошибки или
    None, если заморозка допустима."""
    if freezes_available <= 0:
        return "Заморозки закончились"
    if day > today:
        return "Нельзя заморозить будущий день"
    if day == today:
        return "Сегодняшний день ещё можно закрыть — заморозка не нужна"
    if (today - day).days > FREEZE_MAX_AGE_DAYS:
        return f"Заморозить можно день не старше {FREEZE_MAX_AGE_DAYS} {days_word(FREEZE_MAX_AGE_DAYS)}"
    if status == STATUS_CLOSED:
        return "День уже закрыт"
    if status == STATUS_FROZEN:
        return "День уже заморожен"
    return None
