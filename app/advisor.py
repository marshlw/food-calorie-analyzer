# app/advisor.py
"""AI-советчик (кнопка ✦ в центре навигации).

Собирает контекст пользователя (КБЖУ за день, вода, вес, тренировки),
и формирует советы:
  1. через языковую модель (тот же Yandex Cloud API, что и анализ фото);
  2. при недоступности LLM — детерминированные правила (fallback).

Ответ кэшируется в Redis на короткое время, чтобы не жечь токены при
каждом открытии вкладки.
"""

import asyncio
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from app import crud, models
from app.config import settings

logger = logging.getLogger(__name__)

# Отдельный пул потоков для LLM-вызовов советчика. НЕ общий threadpool
# FastAPI: иначе несколько десятков одновременных запросов советчика
# (по 10-40 секунд каждый) исчерпают общий пул и подвесят весь API.
_llm_executor = ThreadPoolExecutor(
    max_workers=max(1, getattr(settings, "ADVISOR_MAX_CONCURRENCY", 8)),
    thread_name_prefix="advisor-llm",
)

ADVISOR_CACHE_TTL = 30 * 60        # 30 минут — для ответов LLM
ADVISOR_RULES_CACHE_TTL = 2 * 60   # 2 минуты — для rules-фолбэка (чтобы ошибка не «залипала»)
ADVISOR_LLM_TIMEOUT = 40           # сек: qwen с reasoning может думать долго


# ===================== КОНТЕКСТ ПОЛЬЗОВАТЕЛЯ =====================

def build_user_context(db: Session, user: models.User) -> Dict[str, Any]:
    """Снимок дня пользователя — вход и для правил, и для LLM-промпта."""
    today = date.today()
    targets = crud.compute_nutrition_targets(db, user)

    log = crud.get_daily_log(db, user.id, today)
    totals = crud.calculate_daily_totals(log) if log else {
        "total_calories": 0.0, "total_protein": 0.0,
        "total_fat": 0.0, "total_carbs": 0.0,
    }

    water_ml = crud.get_water_total(db, user.id, today)

    workouts = crud.list_workouts(db, user.id, today)
    workout_totals = crud.workouts_day_totals(db, user.id, today)
    week_workout_dates = crud.workout_dates_in_range(
        db, user.id, today - timedelta(days=6), today
    )

    weights = crud.list_weight_history(db, user.id)[-5:]
    weight_trend = None
    if len(weights) >= 2:
        weight_trend = round(weights[-1].weight_kg - weights[0].weight_kg, 1)

    # Цель пользователя: без неё советы получаются «средними по больнице» —
    # один и тот же остаток калорий на похудении и на массе требует прямо
    # противоположных рекомендаций.
    goal_plan = targets.get("goal_plan") or {}

    return {
        "date": today.isoformat(),
        "name": (user.full_name or "").split(" ")[0] or None,
        "goal": {
            "goal": goal_plan.get("goal") or "maintain",
            "rate_kg_per_week": goal_plan.get("applied_rate_kg_per_week"),
            "target_weight_kg": goal_plan.get("target_weight_kg"),
            "calorie_delta": goal_plan.get("calorie_delta"),
            "remaining_kg": goal_plan.get("remaining_kg"),
            "weeks_to_goal": goal_plan.get("weeks_to_goal"),
            "maintenance_calories": targets.get("maintenance_calories"),
        },
        "targets": {
            "calories": targets["calories"],
            "protein_g": targets["protein_g"],
            "fat_g": targets["fat_g"],
            "carbs_g": targets["carbs_g"],
            "water_ml": targets["water_ml"],
        },
        "eaten": {
            "calories": totals["total_calories"],
            "protein_g": totals["total_protein"],
            "fat_g": totals["total_fat"],
            "carbs_g": totals["total_carbs"],
        },
        "water_ml": water_ml,
        "workouts_today": [
            {
                "type": w.workout_type,
                "title": w.title,
                "duration_min": w.duration_min,
                "calories_burned": w.calories_burned,
            }
            for w in workouts
        ],
        "workout_calories_today": workout_totals["total_calories_burned"],
        "workout_days_last_week": len(week_workout_dates),
        "current_weight_kg": targets["current_weight_kg"],
        "weight_trend_kg": weight_trend,
    }


# ===================== ПРАВИЛА (FALLBACK) =====================

def _pct(value: Optional[float], target: Optional[float]) -> Optional[int]:
    if not target:
        return None
    return round(value / target * 100) if value is not None else None


# Подписи цели для текстов советов.
GOAL_LABELS = {"lose": "снижение веса", "maintain": "поддержание веса", "gain": "набор массы"}


def rule_based_advice(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """Детерминированные советы из контекста. Без LLM, работает всегда."""
    t = ctx["targets"]
    e = ctx["eaten"]
    g = ctx.get("goal") or {}
    goal = g.get("goal") or "maintain"
    nutrition: List[Dict[str, str]] = []
    training: List[Dict[str, str]] = []

    headline_title = "Держите темп"
    headline_text = "Записывайте приёмы пищи и тренировки — так советы будут точнее."

    # --- Цель: главный совет по умолчанию + прогноз ---
    if goal != "maintain" and g.get("weeks_to_goal") and g.get("remaining_kg"):
        verb = "сбросить" if goal == "lose" else "набрать"
        headline_title = "Цель в графике"
        headline_text = (
            f"Осталось {verb} {g['remaining_kg']} кг. При текущем темпе "
            f"{round(g['rate_kg_per_week'] * 1000)} г/нед это займёт около "
            f"{round(g['weeks_to_goal'])} нед — держите норму калорий."
        )

    # --- Белок ---
    if t["protein_g"]:
        gap = round(t["protein_g"] - e["protein_g"])
        if gap > 15:
            headline_title = "Не хватает белка"
            headline_text = (
                f"Сегодня {round(e['protein_g'])} г белка из {round(t['protein_g'])} г. "
                f"Добавьте ~{gap} г: творог, рыба или яйца хорошо закроют разницу."
            )
            nutrition.append({
                "title": f"Добавьте ~{gap} г белка до конца дня",
                "text": "Запечённая рыба, индейка или творог впишутся в остаток нормы.",
                "tag": "protein",
            })

    # --- Калории (формулировки зависят от цели) ---
    if t["calories"]:
        remaining = round(t["calories"] + ctx["workout_calories_today"] - e["calories"])
        if remaining > 0:
            texts = {
                # На похудении остаток — это ресурс, который не обязательно
                # «доедать»; на массе — недобор, который цель как раз тормозит.
                "lose": "Хватит на полноценный ужин с белком и овощами. "
                        "Добирать остаток «до нуля» необязательно.",
                "maintain": "С учётом активности сегодня можно спокойно "
                            "поужинать в пределах нормы.",
                "gain": "Для набора этот остаток лучше закрыть: каша с орехами, "
                        "сыр или второй ужин.",
            }
            nutrition.append({
                "title": f"Осталось ~{remaining} ккал на сегодня",
                "text": texts.get(goal, texts["maintain"]),
                "tag": "calories",
            })
        else:
            texts = {
                "lose": f"Превышение ~{abs(remaining)} ккал. Если захочется есть — "
                        "вода и белковый перекус вместо сладкого.",
                "maintain": "Если захочется есть — выбирайте лёгкие белковые "
                            "перекусы и воду.",
                "gain": "Норма закрыта — для набора это ровно то, что нужно. "
                        "Следите, чтобы профицит был регулярным, а не рывками.",
            }
            nutrition.append({
                "title": "Норма калорий на сегодня закрыта",
                "text": texts.get(goal, texts["maintain"]),
                "tag": "calories",
            })

    # --- Вода ---
    if t["water_ml"]:
        water_pct = _pct(ctx["water_ml"], t["water_ml"]) or 0
        if water_pct < 75:
            nutrition.append({
                "title": "Вода отстаёт от нормы",
                "text": (
                    f"Выпито {round(ctx['water_ml'])} из {round(t['water_ml'])} мл. "
                    "Добавьте 1–2 стакана в ближайший час."
                ),
                "tag": "water",
            })

    # --- Тренировки ---
    days = ctx["workout_days_last_week"]
    if ctx["workouts_today"]:
        training.append({
            "title": "Сегодня уже была активность — отлично",
            "text": (
                f"Потрачено ~{round(ctx['workout_calories_today'])} ккал. "
                "После нагрузки помогают белковый приём пищи и вода."
            ),
            "tag": "training",
        })
    if days >= 3:
        training.append({
            "title": "Запланируйте день отдыха",
            "text": (
                f"{days} дней с тренировками за неделю: мышцам нужны 24–48 ч восстановления. "
                "Лёгкая прогулка или растяжка — идеально."
            ),
            "tag": "training",
        })
    elif days == 0:
        training.append({
            "title": "Добавьте лёгкую активность",
            "text": "На этой неделе тренировок ещё не было — начните с 20–30 минут ходьбы.",
            "tag": "training",
        })

    # --- Вес: динамика сверяется с направлением цели ---
    if ctx["weight_trend_kg"] is not None and goal != "maintain":
        trend = ctx["weight_trend_kg"]
        expected_sign = -1 if goal == "lose" else 1
        if trend != 0 and (trend > 0) == (expected_sign > 0):
            training.append({
                "title": "Динамика веса работает на цель",
                "text": (
                    f"За последние записи {trend:+.1f} кг — направление верное "
                    f"для цели «{GOAL_LABELS[goal]}»."
                ),
                "tag": "general",
            })
        elif trend != 0:
            training.append({
                "title": "Вес идёт против цели",
                "text": (
                    f"За последние записи {trend:+.1f} кг при цели "
                    f"«{GOAL_LABELS[goal]}». Одна-две недели — ещё не тренд, "
                    "но стоит проверить полноту записей в дневнике."
                ),
                "tag": "general",
            })

    return {
        "headline_title": headline_title,
        "headline_text": headline_text,
        "nutrition": nutrition[:3],
        "training": training[:3],
        "generated_by": "rules",
    }


# ===================== LLM =====================

def _get_llm_client():
    """Текстовый клиент к Yandex Cloud (тот же API, что и анализ фото)."""
    if not settings.YANDEX_API_KEY or not settings.YANDEX_FOLDER_ID:
        return None
    from openai import OpenAI
    return OpenAI(
        api_key=settings.YANDEX_API_KEY,
        base_url=settings.YANDEX_API_URL,
        project=settings.YANDEX_FOLDER_ID,
        timeout=ADVISOR_LLM_TIMEOUT,
    )


def _extract_responses_text(response) -> Optional[str]:
    """Достаёт текст из ответа Responses API (как в ml_service)."""
    text = getattr(response, "output_text", None)
    if text and text.strip():
        return text
    try:
        dump = response.model_dump()
    except Exception:
        return None
    chunks: list = []
    for item in dump.get("output", []) or []:
        # Пропускаем блок рассуждений — нам нужен только итоговый текст
        if item.get("type") == "reasoning":
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, dict) and part.get("text"):
                chunks.append(part["text"])
    return "\n".join(chunks) if chunks else None


def _llm_complete(instructions: str, prompt: str) -> Optional[str]:
    client = _get_llm_client()
    if client is None:
        logger.warning("Advisor LLM disabled: YANDEX_API_KEY/FOLDER_ID not configured")
        return None

    model = f"gpt://{settings.YANDEX_FOLDER_ID}/{settings.YANDEX_VISION_MODEL}"

    # 1) Responses API (как у анализа фото). Бюджет токенов берём из настроек:
    # у reasoning-моделей «мысли» съедают бюджет, при малом лимите ответ
    # обрывается до JSON — из-за этого советчик уходил в fallback.
    try:
        response = client.responses.create(
            model=model,
            temperature=0.2,
            max_output_tokens=getattr(settings, "YANDEX_MAX_OUTPUT_TOKENS", 4000),
            reasoning={"effort": getattr(settings, "YANDEX_REASONING_EFFORT", "low")},
            instructions=instructions,
            input=[{
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }],
        )
        text = _extract_responses_text(response)
        if text:
            return text
        logger.warning(
            "Advisor LLM: empty text from Responses API (status=%s)",
            getattr(response, "status", None),
        )
    except Exception:
        logger.warning("Advisor LLM: Responses API call failed", exc_info=True)

    # 2) Fallback: классический chat.completions (тоже поддерживается Yandex)
    try:
        completion = client.chat.completions.create(
            model=model,
            temperature=0.2,
            max_tokens=2000,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": prompt},
            ],
        )
        text = (completion.choices[0].message.content or "").strip()
        if text:
            return text
        logger.warning("Advisor LLM: empty text from chat.completions")
    except Exception:
        logger.warning("Advisor LLM: chat.completions call failed", exc_info=True)

    return None


_ADVICE_INSTRUCTIONS = """
Ты — заботливый советчик по питанию и тренировкам в приложении-дневнике Rasify.
Тебе дают JSON с данными пользователя за сегодня (цель по весу, нормы КБЖУ,
съедено, вода, тренировки, динамика веса).

Поле goal — главный ориентир. goal.goal = "lose" (снижение веса),
"maintain" (поддержание) или "gain" (набор массы); goal.calorie_delta — на
сколько ккал суточная норма уже отличается от нормы поддержания. Норма в
targets УЖЕ учитывает цель — не предлагай «дополнительно урезать» или
«добавить сверху». Советы должны соответствовать цели: при снижении веса —
сытость, белок и объём пищи; при наборе — как добрать калории; при
поддержании — стабильность и качество рациона. Если есть goal.weeks_to_goal,
можешь упомянуть срок.

Верни ТОЛЬКО JSON без markdown по схеме:
{
  "headline_title": "короткий заголовок главного совета (до 40 символов)",
  "headline_text": "главный совет дня, 1-2 предложения, с конкретными цифрами",
  "nutrition": [{"title": "...", "text": "...", "tag": "protein|water|calories|carbs|general"}],
  "training": [{"title": "...", "text": "...", "tag": "training|general"}]
}

Правила: пиши по-русски, дружелюбно и конкретно (с цифрами из данных),
не выдумывай данные, максимум 3 совета в каждом списке, без медицинских
диагнозов и жёстких ограничений.
"""


def _parse_llm_advice(raw: Optional[str]) -> Optional[Dict[str, Any]]:
    if not raw:
        return None
    try:
        from app.ml_service import extract_json
        data = extract_json(raw)
    except Exception:
        data = None
    if not isinstance(data, dict):
        return None
    if not data.get("headline_title") or not data.get("headline_text"):
        return None

    def _tips(items) -> List[Dict[str, str]]:
        result = []
        for item in (items or [])[:3]:
            if isinstance(item, dict) and item.get("title") and item.get("text"):
                result.append({
                    "title": str(item["title"])[:120],
                    "text": str(item["text"])[:400],
                    "tag": str(item.get("tag") or "general"),
                })
        return result

    return {
        "headline_title": str(data["headline_title"])[:80],
        "headline_text": str(data["headline_text"])[:500],
        "nutrition": _tips(data.get("nutrition")),
        "training": _tips(data.get("training")),
        "generated_by": "llm",
    }


# ===================== КЭШ =====================

def _cache_key(user_id: int, ctx: Dict[str, Any]) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(ctx, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    # v2: старые записи v1 (rules могли закэшироваться на 30 мин) игнорируются
    return f"advisor:v2:{user_id}:{ctx['date']}:{fingerprint}"


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    try:
        from app.ml_service import get_redis_client
        raw = get_redis_client().get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    try:
        from app.ml_service import get_redis_client
        # Rules-фолбэк кэшируем совсем ненадолго: как только LLM снова доступна,
        # пользователь должен получить «живые» советы, а не залипший фолбэк.
        ttl = ADVISOR_CACHE_TTL if payload.get("generated_by") == "llm" else ADVISOR_RULES_CACHE_TTL
        get_redis_client().setex(key, ttl, json.dumps(payload, ensure_ascii=False))
    except Exception:
        pass


# ===================== ПУБЛИЧНОЕ API МОДУЛЯ =====================

def prepare_advice(db: Session, user: models.User) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any], str]:
    """Быстрая часть (только БД): контекст дня + проверка кэша.
    Возвращает (кэшированный ответ или None, контекст, ключ кэша).
    Выполняется в обычном threadpool — БД-запросы занимают миллисекунды."""
    ctx = build_user_context(db, user)
    key = _cache_key(user.id, ctx)
    return _cache_get(key), ctx, key


def generate_advice(ctx: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Медленная часть (LLM, БЕЗ БД — не держит коннект из пула на время
    вызова модели). Запускается в выделенном _llm_executor."""
    prompt = "Данные пользователя за сегодня:\n" + json.dumps(ctx, ensure_ascii=False, indent=2)
    raw = _llm_complete(_ADVICE_INSTRUCTIONS, prompt)
    advice = _parse_llm_advice(raw)
    if advice is None:
        if raw:
            logger.warning("Advisor LLM: failed to parse advice JSON, raw=%r", raw[:500])
        advice = rule_based_advice(ctx)

    _cache_set(key, advice)
    return advice


def get_advice(db: Session, user: models.User) -> Dict[str, Any]:
    """Советы для вкладки AI-советчика: LLM → (при ошибке) правила.
    Синхронная версия (тесты/скрипты); эндпоинты используют get_advice_async."""
    cached, ctx, key = prepare_advice(db, user)
    if cached:
        return cached
    return generate_advice(ctx, key)


async def get_advice_async(db: Session, user: models.User) -> Dict[str, Any]:
    """Async-обёртка для эндпоинта: БД — в общем threadpool (быстро),
    LLM — в выделенном пуле советчика (долго, но не мешает другим запросам)."""
    from starlette.concurrency import run_in_threadpool

    cached, ctx, key = await run_in_threadpool(prepare_advice, db, user)
    if cached:
        return cached
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_llm_executor, generate_advice, ctx, key)


_ASK_INSTRUCTIONS = """
Ты — советчик по питанию и тренировкам в приложении-дневнике Rasify.
Пользователь задаёт вопрос; тебе также передают JSON с его данными за сегодня.
Ответь по-русски, дружелюбно и коротко (до 120 слов), опираясь на данные.
Не ставь диагнозы и не назначай лечение. Верни просто текст без markdown.
"""


def generate_answer(ctx: Dict[str, Any], question: str) -> Dict[str, str]:
    """Медленная часть свободного вопроса (LLM, без БД).
    Запускается в выделенном _llm_executor."""
    prompt = (
        f"Вопрос пользователя: {question}\n\n"
        "Данные за сегодня:\n" + json.dumps(ctx, ensure_ascii=False, indent=2)
    )
    answer = _llm_complete(_ASK_INSTRUCTIONS, prompt)
    if answer:
        # Убираем возможный блок рассуждений reasoning-модели (<think>…</think>)
        answer = re.sub(r"<think>.*?</think>", "", answer, flags=re.DOTALL).strip()
    if answer:
        return {"answer": answer[:2000], "generated_by": "llm"}

    # Fallback: краткая сводка по правилам
    advice = rule_based_advice(ctx)
    parts = [advice["headline_text"]]
    for tip in (advice["nutrition"] + advice["training"])[:2]:
        parts.append(f"{tip['title']}. {tip['text']}")
    return {
        "answer": "AI сейчас недоступен, вот сводка по вашим данным: " + " ".join(parts),
        "generated_by": "rules",
    }


def ask(db: Session, user: models.User, question: str) -> Dict[str, str]:
    """Свободный вопрос советчику («что съесть перед тренировкой?»).
    Синхронная версия; эндпоинт использует ask_async."""
    ctx = build_user_context(db, user)
    return generate_answer(ctx, question)


async def ask_async(db: Session, user: models.User, question: str) -> Dict[str, str]:
    """Async-обёртка: контекст — в общем threadpool, LLM — в пуле советчика."""
    from starlette.concurrency import run_in_threadpool

    ctx = await run_in_threadpool(build_user_context, db, user)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_llm_executor, generate_answer, ctx, question)
