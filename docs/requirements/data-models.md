# Модели данных — AI Healthy

Описание сущностей БД (SQLAlchemy) и схем обмена (Pydantic). Для каждой сущности указаны
поля, типы, ограничения и связи — основа для генерации тестовых данных и проверки контрактов.

---

## Перечисления (Enum)

| Enum | Значения | Назначение |
|------|----------|-----------|
| `TaskStatus` | `pending`, `processing`, `success`, `failure` | Статус задачи анализа изображения |
| `FeedbackStatus` | `pending`, `used` | Статус обработки фидбека |
| `sex` | `male`, `female` | Пол пользователя |
| `activity_level` | `sedentary`, `light`, `moderate`, `active`, `very_active` | Уровень физической активности |
| `meal_type` | `breakfast`, `lunch`, `dinner`, `snacks` | Тип приёма пищи |
| `weight source` | `manual`, `registration`, `profile_edit` | Источник записи о взвешивании |

---

## Сущности базы данных

### User (`users`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `email` | string | уникальный, обязательный, индекс |
| `hashed_password` | string | обязательный (bcrypt, наружу не отдаётся) |
| `full_name` | string | nullable |
| `is_active` | bool | по умолчанию `true` |
| `created_at` | datetime | server default `now()` |
| `height_cm` | float | nullable |
| `sex` | string | nullable (`male`/`female`) |
| `birth_date` | date | nullable |
| `activity_level` | string | nullable |

**Связи:** `meals` (1:N, cascade), `tasks` (1:N), `daily_logs` (1:N, cascade), `weight_records` (1:N, cascade).
**Примечание:** текущий вес НЕ хранится в `users` — источник правды — последняя запись `weight_records`.

---

### WeightRecord (`weight_records`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `weight_kg` | float | обязательный |
| `recorded_on` | date | обязательный, server default `current_date()` |
| `note` | string | nullable |
| `source` | string | по умолчанию `manual` |
| `created_at` | datetime | server default `now()` |

**Ограничение целостности:** `UniqueConstraint(user_id, recorded_on)` — одна запись на пользователя в день (защита от дублей через upsert).

---

### DailyLog (`daily_logs`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный |
| `date` | date | обязательный, индекс, server default `current_date()` |

**Связи:** `entries` (1:N → MealEntry, cascade). Создаётся лениво при первом приёме пищи за день.

---

### MealEntry (`meal_entries`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `daily_log_id` | int | FK → daily_logs.id, обязательный |
| `food_name` | string | обязательный |
| `calories` | float | обязательный |
| `protein_g` | float | обязательный |
| `fat_g` | float | обязательный |
| `carbs_g` | float | обязательный |
| `weight_g` | float | обязательный |
| `meal_type` | string | по умолчанию `snacks` |
| `task_id` | string | FK → tasks.id, nullable (заполнен → запись из AI-анализа) |
| `created_at` | datetime | server default `now()` |

---

### Task (`tasks`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | string (UUID) | PK |
| `user_id` | int | FK → users.id, обязательный |
| `image_path` | string | обязательный (на диске; наружу — URL `/uploads/<file>`) |
| `status` | enum TaskStatus | по умолчанию `pending` |
| `result_json` | text | nullable (JSON результата анализа) |
| `error` | text | nullable |
| `image_hash` | string | nullable, индекс (для кэширования) |
| `created_at` | datetime | server default `now()` |
| `updated_at` | datetime | onupdate `now()` |

**Примечание:** свойство `result` модели возвращает `result_json`; схема `TaskResponse` парсит его в объект `NutritionResponse`.

---

### Feedback (`feedback`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `task_id` | string | FK → tasks.id, обязательный, индекс |
| `image_path` | string | обязательный |
| `predicted_result` | JSON | nullable (что предсказала модель) |
| `corrected_food` | string | обязательный |
| `corrected_weight` | int | обязательный |
| `user_id` | int | FK → users.id, обязательный |
| `created_at` | datetime | server default `now()` |
| `status` | enum FeedbackStatus | по умолчанию `pending` |

---

### Product (`products`)

Справочник КБЖУ (нутриенты на 100 г), используется ML-сервисом.

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `name` | string | уникальный, обязательный, индекс |
| `calories` | float | обязательный |
| `protein` | float | обязательный |
| `fat` | float | обязательный |
| `carbs` | float | обязательный |
| `created_at` | datetime | server default `now()` |

---

### Meal / MealItem / Photo (legacy)

Сущности `meals`, `meal_items`, `photos` присутствуют в модели данных (агрегаты приёмов
пищи и фото-вложения), но в текущем наборе REST-эндпоинтов напрямую не используются —
актуальный учёт ведётся через `DailyLog` + `MealEntry`. Учитывать при проверке миграций БД.

---

## Схемы обмена (Pydantic / контракты API)

### Аутентификация

**`AuthRequest`** (вход в `/login`, `/token`)
- `email`: email, опционально (обязателен при `grant_type=password`)
- `password`: string, опционально (обязателен при `grant_type=password`)
- `grant_type`: string, по умолчанию `password` (`password` | `refresh_token`)
- `refresh_token`: string, опционально (обязателен при `grant_type=refresh_token`)

**`Token`** (ответ)
- `access_token`: string
- `refresh_token`: string | null
- `token_type`: `bearer`

**`UserCreate`** (регистрация)
- `email`: email, обязательный
- `full_name`: string | null
- `password`: string, **min_length=8**, обязательный
- `height_cm`: float, `0 < x < 300`, опционально
- `weight_kg`: float, `0 < x < 300`, опционально

**`User`** (ответ)
- `id`: int, `email`: email, `full_name`: string|null, `is_active`: bool, `created_at`: datetime

---

### Профиль и вес

**`ProfileUpdate`** (PUT профиля) — все поля опциональны
- `full_name`: string|null
- `height_cm`: float `0<x<300`
- `weight_kg`: float `0<x<300`
- `sex`: `male`|`female`
- `birth_date`: date
- `activity_level`: `sedentary`|`light`|`moderate`|`active`|`very_active`
- `save_weight_as_record`: bool, по умолчанию `true`

**`ProfileResponse`**
- `id`, `email`, `full_name`, `height_cm`, `current_weight_kg`, `sex`, `birth_date`, `activity_level`
- `recent_weights`: список `WeightRecordResponse` (последние ~30)
- `bmr`: float|null, `daily_calorie_target`: float|null
- `protein_target_g`, `fat_target_g`, `carbs_target_g`: float|null

**`WeightRecordCreate`**
- `weight_kg`: float `0<x<300`, обязательный
- `recorded_on`: date, опционально (по умолчанию сегодня)
- `note`: string, max 200, опционально

**`WeightRecordResponse`**
- `id`, `weight_kg`, `recorded_on`, `note`|null, `source`

---

### Анализ и задачи

**`TaskCreatedResponse`** (ответ `/analyze`)
- `id`: string, `status`: string

**`NutritionResponse`** (результат анализа внутри задачи)
- `food`: string, обязательный
- `weight_g`: float, `0.1 ≤ x ≤ 5000`
- `calories`: float, `0 ≤ x ≤ 10000`
- `protein_g`: float, `≥ 0`
- `fat_g`: float, `≥ 0`
- `carbs_g`: float, `≥ 0`
- `confidence`: float, `0 ≤ x ≤ 1`
- `note`: string|null
- `ingredients`: список `IngredientResponse`

**`IngredientResponse`**
- `name`: string, `type`: string (`protein`|`carb`|`fat`|`vegetable`|`unknown`), `weight_g`: float

**`TaskResponse`**
- `id`: string, `status`: string
- `result`: `NutritionResponse`|null
- `image_path`: string|null (отдаётся как URL `/uploads/<file>`)
- `error`: string|null
- `created_at`: datetime, `updated_at`: datetime|null

---

### Дневник питания

**`MealEntryCreate`**
- `food_name`: string, обязательный
- `calories`, `protein_g`, `fat_g`, `carbs_g`: float `≥ 0`
- `weight_g`: float `> 0`
- `meal_type`: string, по умолчанию `snacks`
- `date`: date, опционально (по умолчанию сегодня)
- `task_id`: string, опционально

**`MealEntryResponse`**
- `id`, `food_name`, `calories`, `protein_g`, `fat_g`, `carbs_g`, `weight_g`, `meal_type`, `created_at`, `task_id`|null

**`AnalysisMealRequest`** (`/meals/from-analysis`)
- `task_id`: string, обязательный
- `meal_type`: string, по умолчанию `snacks`

**`DailyLogResponse`**
- `date`: date
- `total_calories`, `total_protein`, `total_fat`, `total_carbs`: float
- `meals`: список `MealEntryResponse`
- `targets`: `NutritionTargets` (`calories`, `protein_g`, `fat_g`, `carbs_g`)

---

### Обратная связь

**`FeedbackRequest`**
- `task_id`: string, обязательный
- `correct_food`: string, **1..200 символов**
- `correct_weight`: int, **`0 < x ≤ 10000`**

**`FeedbackResponse`**
- `status`: string, `id`: int

**`FeedbackListItem`** (админка)
- `id`, `task_id`, `image_path`, `predicted_result` (object|null), `corrected_food`, `corrected_weight`, `user_id`|null, `created_at`, `status`

---

## Связанные документы

- [Функциональные требования](functional-requirements.md)
- [Бизнес-правила](business-rules.md)
- [OpenAPI спецификация](../api/swagger.yaml)
