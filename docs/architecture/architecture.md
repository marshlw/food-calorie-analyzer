# AI Healthy — System Architecture

## Overview

AI Healthy is a nutrition-tracking app: photograph a meal, get automatic KBJU (calories/protein/
fat/carbs) recognition, plus a full diary (manual entries, barcode scanning, water, workouts) and
an AI advisor. Clients are a React web app (PWA) and a Telegram bot, both talking to the same
FastAPI backend.

**Key components:**
- FastAPI REST API (Python), package root `app/` (flat layout — see [code audit](code_audit.md))
- PostgreSQL database (SQLAlchemy, synchronous engine)
- Celery task queue + Redis (broker, cache, rate-limit counters, bot token storage)
- Multi-provider ML vision pipeline (Yandex Cloud / Gemini / DeepSeek / Ollama) for photo analysis
- Yandex Cloud LLM for the AI advisor (text-only, same account as vision)
- Telegram bot (aiogram) as an alternate client
- React 18 + TypeScript + Vite frontend, served as static files by the same FastAPI app

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                  │
├───────────────────────────────┬───────────────────────────────────────┤
│  Telegram Bot (aiogram)        │  React SPA / PWA (Vite, served by API) │
└───────────────┬─────────────────┴───────────────────┬───────────────────┘
                │  HTTP (APIClient)                    │  HTTP (axios)
                └────────────────────┬───────────────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   FastAPI (app/main.py)│
                          │   uvicorn, port 8000    │
                          ├─────────────────────────┤
                          │ auth · profile · diary   │
                          │ water · workouts · barcode│
                          │ analyze · advisor · admin │
                          └──────────┬──────────────┘
                                     │ SQLAlchemy (sync)
              ┌──────────────────────┼───────────────────────┐
              │                      │                       │
     ┌────────▼────────┐   ┌─────────▼─────────┐   ┌──────────▼─────────┐
     │   PostgreSQL     │   │       Redis        │   │   Celery worker     │
     │  (source of truth)│   │ • ML result cache  │   │ (app/celery_app.py) │
     │  users, tasks,    │   │ • advisor cache     │   │ analyze_image_task  │
     │  diary, workouts, │   │ • rate-limit counters│  │ retrain_model_task* │
     │  products, ...    │   │ • bot token storage  │  │ (* currently broken,│
     └──────────────────┘   │   (tg_tokens:*)      │  │   see code audit)   │
                             └──────────┬───────────┘  └──────────┬──────────┘
                                        │ also reads/writes DB via SQLAlchemy │
                                        └──────────────────────────┬──────────┘
                                                                    │
                                                        ┌───────────▼────────────┐
                                                        │   ML provider chain     │
                                                        │  (app/ml_service.py)     │
                                                        ├──────────────────────────┤
                                                        │ order = MODEL_PROVIDER   │
                                                        │ first, then the rest:    │
                                                        │ yandex → gemini →        │
                                                        │ deepseek → ollama        │
                                                        │ (default MODEL_PROVIDER  │
                                                        │  = "yandex")             │
                                                        │ each wrapped in a        │
                                                        │ CircuitBreaker           │
                                                        └──────────────────────────┘
```

A dedicated diagram of exactly how each backend component talks to PostgreSQL — including which
tables each one reads/writes — lives in
[`db-backend-interaction.md`](db-backend-interaction.md).

---

## Component Details

### 0. Package Layout

The backend is a **flat package** at `app/` (`app/main.py`, `app/models.py`, `app/crud.py`, ...).
`app/app/` is **not** a code package — it only holds `tests/` (pytest suite), `uploads/`
(user-submitted photos, served via signed URLs), and `training_data/` (small dataset for the
model-retraining feature, currently broken — see [code audit](code_audit.md)).

### 1. FastAPI Application (`app/main.py`)

Central REST API serving both the React frontend and the Telegram bot. In production
(`ENABLE_DOCS=false`, the default) Swagger UI/OpenAPI JSON/ReDoc are disabled so the API surface
isn't exposed to the public internet; set `ENABLE_DOCS=true` locally to browse `/docs`.

**Endpoint groups** (full table: [api-endpoints-summary.md](../api/api-endpoints-summary.md)):
auth (`/register`, `/login`, `/token`, `/me`, `/change-password`), profile & weight history,
products & barcode lookup, photo analysis (`/analyze`, `/task/{id}`, `/tasks`), diary
(`/meals*`, `/daily-log`), water, workouts & exercises, AI advisor, feedback, admin (feedback
moderation, gated by `X-Admin-Token`), and a signed `/uploads/{filename}` file server.

**CORS:** explicit allow-list (`settings.ALLOWED_ORIGINS` + `ALLOWED_ORIGINS_EXTRA` from env) —
not a wildcard.

**Static frontend:** if `app/static/frontend` exists (populated by the frontend build step), it's
mounted at `/` with SPA fallback (`SPAStaticFiles`) so React Router routes work on direct
navigation/refresh; unknown non-API paths get `index.html`, unknown API paths get a real `404`.

### 2. Authentication (`app/auth.py`)

JWT access/refresh tokens; bcrypt password hashing (72-byte truncation); password-change bumps
`token_version` to instantly revoke previously issued tokens. Full detail:
[auth_flow.md](auth_flow.md).

- Access token: 30 minutes (`ACCESS_TOKEN_EXPIRE_MINUTES`)
- Refresh token: 7 days (`REFRESH_TOKEN_EXPIRE_DAYS`)

### 3. ML Service (`app/ml_service.py`)

**Architecture:** dynamic provider chain with circuit breaker, retries, and caching.

```
MODEL_PROVIDER (default "yandex") first, then the remaining three:

┌──────────┐      ┌─────────────┐      ┌──────────────┐      ┌────────────┐      ┌──────────┐
│  Yandex  │─────►│   Gemini    │─────►│   DeepSeek   │─────►│   Ollama   │─────►│ Fallback │
│(default) │      │             │      │              │      │  (local)   │      │  (safe)  │
└──────────┘      └─────────────┘      └──────────────┘      └────────────┘      └──────────┘
```

Each provider is wrapped in a `CircuitBreaker` (3 consecutive failures → 300s cooldown) and
retried up to `MODEL_RETRY_ATTEMPTS` (2) times with backoff; quota/429 errors abort retries early.
If every provider fails, `DEFAULT_FALLBACK` is used — and is treated as a **successful** task
result (`source: "fallback"`), not an error.

**Caching:** Redis key `f"{CACHE_PREFIX}:{PROMPT_VERSION}:{sha256(image)}"` — currently
`food_analysis:v4:v15:<hash>` — TTL `CACHE_TTL` (24h). Bump `PROMPT_VERSION` in code to invalidate
old cache entries after a prompt change.

**Result shape** (also stored as `Task.result_json`):

```json
{
  "food": "паста карбонара",
  "weight_g": 300,
  "confidence": 0.92,
  "calories": 450, "protein_g": 18, "fat_g": 22, "carbs_g": 35,
  "protein_animal_g": 12, "protein_plant_g": 2,
  "ingredients": [{"name": "паста", "type": "carb", "weight_g": 150, "protein_type": "plant"}],
  "source": "yandex",
  "models_tried": ["yandex"],
  "processing_time_sec": 2.34
}
```

`calc_kbju()` looks each ingredient up in the `products` table (falling back to a per-type
nutrient estimate if not found) and additionally splits protein into animal/plant using
`protein_source.split_protein()` based on the product's `protein_type` tag.
`_clamp_calorie_density()` caps the result at 600 kcal/100g to guard against over-estimation.

### 4. Task Queue (`app/tasks.py`, `app/celery_app.py`)

Celery worker (broker + result backend = Redis) runs `analyze_image_task` asynchronously so the
`POST /analyze` HTTP request isn't blocked by ML latency. Lifecycle detail:
[task_lifecycle.md](task_lifecycle.md). A second task, `retrain_model_task`, exists for
Ollama-based model retraining but currently fails (`generate_dataset.py` references a config field
that no longer exists — see [code audit](code_audit.md)); it's triggered when ≥10 feedback rows
accumulate in `pending` status but the retrain itself will error out.

### 5. Database Schema (`app/models.py`)

Full field-level reference: [data-models.md](../requirements/data-models.md). Summary of the
active tables (current diary/tracking flow):

- `users` — account + profile fields (height, sex, birth date, activity level) + optional manual
  `custom_*` nutrition/water target overrides + `token_version`
- `weight_records` — one row per (user, date); also carries body measurements (waist/chest/hips/
  shoulders); source of truth for "current weight" (no separate column on `users`)
- `daily_logs` / `meal_entries` / `meal_entry_items` — the diary: one `daily_logs` row per
  (user, date), each with `meal_entries` (simple or composite via `items`), including protein
  animal/plant split and an optional manually-attached photo
- `water_logs` — one row per (user, date), ml
- `workouts` / `workout_items` — training diary, optionally composite; `exercises` — reference
  table of kcal/min by exercise, seeded at startup
- `tasks` — one row per photo-analysis job (`TaskStatus`: pending/processing/success/failure),
  `result_json` = the ML result shape above
- `feedback` — user corrections to analysis results, feeds the (currently broken) retraining loop
- `products` — KBJU-per-100g reference table + `protein_type` tag, seeded at startup, used by both
  `ml_service.calc_kbju` and the `/api/v1/products` search endpoint
- `meals` / `meal_items` / `photos` — **legacy**, not used by any current endpoint; keep in mind
  for migrations but ignore for new work

`app/database.py`'s `ensure_schema()` runs `create_all()` (creates missing tables) plus a manual
idempotent `ALTER TABLE ADD COLUMN`/`CREATE INDEX` step for columns/indexes added after the
original `create_all()` was run in production — there is no Alembic migration tool in this repo.

### 6. AI Advisor (`app/advisor.py`)

`GET /api/v1/advisor` and `POST /api/v1/advisor/ask` build a context snapshot from the DB
(nutrition targets, today's diary totals, water, workouts, recent weight trend) and send it to the
**same Yandex Cloud LLM account** used for photo analysis (text-only call, `client.responses.create`
with a `chat.completions` fallback). If the LLM is unavailable or returns something unparseable,
`rule_based_advice()` produces deterministic advice from the same context (protein gap, calories
remaining, water %, workout streak, weight trend) — the feature always returns *something*, never
a hard error. Responses are cached in Redis per `advisor:v2:{user_id}:{date}:{context_fingerprint}`
(30 min TTL for LLM answers, 2 min for the rules fallback).

### 7. Telegram Bot (`app/telegram_bot.py`, `app/api_client.py`)

Alternate client for the same API — not a separate backend. Auto-registers each Telegram user
(`{telegram_id}@tg.local`) with a **random** password stored in Redis (not the Telegram ID — see
[auth_flow.md](auth_flow.md) for the security rationale and the legacy-account migration path).
Tokens are cached in Redis (`tg_tokens:{user_id}`) to survive bot restarts. Photo upload → poll
`GET /task/{id}` → present result with ✅/❌ feedback buttons → `POST /feedback`.

### 8. Frontend (`frontend/`)

React 18 + TypeScript + Vite + Tailwind CSS + React Router v6 + axios + recharts, no external
state-management library (React Context + hooks only: `AuthContext`, `DiaryContext`). Talks to
the backend via `frontend/src/api/*.ts` (`axios.ts` centralizes the base URL — relative/same-origin
in production, `VITE_API_URL` locally — and JWT attach/refresh via interceptors). In production the
build output (`npm run build` → `dist/`) is copied into `app/static/frontend` and served by
FastAPI itself (see §1) — there is no separate frontend server in production.

---

## Data Flow: Image Analysis

1. **Client** (bot or web) uploads a photo → `POST /api/v1/analyze` (after checking
   `GET /analyze/limit`, a per-user daily quota, default 5/day).
2. **FastAPI** validates the file (extension, real image content, ≤10MB), saves it under
   `UPLOAD_DIR` with a random UUID filename, creates a `Task` row (`status=pending`), enqueues
   `analyze_image_task.delay(...)`.
3. **Celery worker** sets `status=processing`, calls `ml_service.analyze_image_sync()`.
4. **ML service**: check Redis cache by image hash → try providers in `MODEL_PROVIDER`-first order
   → on success, look up ingredient nutrients in `products` (fallback to per-type estimate) → cap
   calorie density → cache result (24h) → return.
5. **Celery worker** sets `status=success`, stores `result_json`. Uploaded file is kept by default
   (needed for the result screen / feedback attachment) unless `DELETE_UPLOAD_AFTER_ANALYSIS=true`.
6. **Client** polls `GET /task/{id}` until `success`/`failure`, then optionally
   `POST /meals/from-analysis` to save it to the diary, and/or `POST /feedback` to correct it.

---

## Error Handling

### Model failures

| Scenario | Behavior | Task status |
|----------|----------|-------------|
| Provider returns invalid/unparseable JSON | Try next provider | `pending` |
| Provider quota exceeded (429) | Skip retries for that provider, try next | `pending` |
| All providers fail | Return `DEFAULT_FALLBACK` | **`success`** ✅ |
| Uploaded file is not a valid image | Rejected at upload time (`400`), no task created | — |
| Celery task raises after enqueue | Retries up to 3x with backoff, then `failure` | `failure` |

### Authentication

| Scenario | Response |
|----------|----------|
| Missing/invalid token | `401` |
| Expired access token | Client should refresh via `POST /token` (`grant_type=refresh_token`) |
| Token issued before a password change (`tv` mismatch) | `401`, even if not technically expired |
| Expired/invalid refresh token | `401`, user must log in again |
| Invalid credentials | `401` |

---

## Configuration (`app/config.py`)

Pydantic `Settings`, loaded from `.env` (not committed). Key groups: `DATABASE_URL` +
`DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, `REDIS_URL`, per-provider ML settings
(`MODEL_PROVIDER`, `YANDEX_*`, `GEMINI_*`, `DEEPSEEK_*`, `OLLAMA_*`), `SECRET_KEY` (startup fails
on placeholder values unless `ALLOW_INSECURE_SECRET_KEY=true`), `ALLOWED_ORIGINS`
(+`ALLOWED_ORIGINS_EXTRA`), upload/image limits, rate-limit thresholds (auth brute-force,
registration, AI daily quota, advisor daily quota, barcode daily quota), `CACHE_TTL`/`CACHE_PREFIX`,
Celery broker/backend URLs, `ADMIN_TOKEN` (unset = admin endpoints return `404`).

---

## Performance Considerations

- **Caching:** SHA-256 image hash as cache key, 24h TTL, versioned by `PROMPT_VERSION` so a prompt
  change doesn't serve stale results.
- **Rate limiting:** implemented once, centrally, in `app/rate_limit.py` (Redis fixed-window
  counters with in-memory fallback if Redis is briefly unavailable) — covers login/register
  brute-force protection and daily quotas for AI analysis, barcode scanning, and the advisor. (A
  separate, unrelated per-provider throttling helper inside `ml_service.py` exists but is dead
  code — see [code audit](code_audit.md).)
- **Database:** synchronous SQLAlchemy engine (not asyncpg), connection pool sized per-process via
  `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`, indexes on the main foreign keys and status/date columns (see
  `ensure_schema()`'s `_ENSURE_INDEXES`).

---

## Testing

Test suite lives in `app/app/tests/`: `test_api.py`, `test_ml_service.py`, `test_ml_contract.py`,
`test_profile.py`, `test_telegram_bot.py`, `conftest.py`. Run with `pytest app/app/tests -v` (no
pass/fail counts are recorded here — see [code audit](code_audit.md) for why, and re-run locally
before relying on any specific number).

---

## Deployment

**Current state of this repository:** `Dockerfile` and `requirements.txt` are present at the repo
root and match what [docs/setup/DOCKER.md](../setup/DOCKER.md) describes (multi-stage build: Node
18 builds the frontend, then Python 3.10-slim-bullseye runs the API with the built frontend copied
into `app/static/frontend`) — `docker build -t ai-healthy .` should work as-is. What's **missing**
is `docker-compose.yml`/`docker-compose-prod.yml` to orchestrate the API alongside PostgreSQL,
Redis, Celery, and (optionally) Ollama — see [code audit](code_audit.md). Until those are added,
either run each container manually with `docker run`, or run everything locally without Docker
(Python venv + `uvicorn`, `celery -A app.celery_app worker`, `npm run dev` for the frontend — see
DOCKER.md's "Local run without Docker" section).

```yaml
# Intended compose shape — file not currently in the repo:
services:
  api:        { build: ".", ports: ["8000:8000"], depends_on: [db, redis] }
  celery:     { build: ".", command: "celery -A app.celery_app worker", depends_on: [db, redis] }
  db:         { image: "postgres:15" }
  redis:      { image: "redis:7" }
  ollama:     { image: "ollama/ollama" }   # only needed if MODEL_PROVIDER involves ollama
  telegram_bot: { build: ".", command: "python -m app.telegram_bot", depends_on: [api, redis] }
```

---

## Future Improvements

1. Add `docker-compose.yml`/`docker-compose-prod.yml` for local/prod orchestration (`Dockerfile`
   and `requirements.txt` already exist and work).
2. Fix or remove the model-retraining pipeline (`generate_dataset.py` references a stale config
   field).
3. Move `@app.on_event` to FastAPI `lifespan` handlers; migrate `ml_service.py`'s Pydantic
   validators to v2 `@field_validator`.
4. Add Alembic (or similar) instead of the hand-rolled `ensure_schema()` column-patching.
5. Per-user API rate limits beyond the current IP/user daily-quota checks.
6. Analytics on model accuracy / provider usage patterns (the data — `models_tried`, `source` per
   task, plus `feedback` corrections — already exists in the DB; no reporting is built on it yet).
