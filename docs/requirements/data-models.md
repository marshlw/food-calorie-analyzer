# Модели данных — AI Healthy

Описание сущностей БД (SQLAlchemy, `app/models.py`) и схем обмена (Pydantic, `app/schemas.py`).
Для каждой сущности указаны поля, типы, ограничения и связи — основа для генерации тестовых
данных и проверки контрактов.

---

## Перечисления (Enum)

| Enum | Значения | Назначение |
|------|----------|-----------|
| `TaskStatus` | `pending`, `processing`, `success`, `failure` | Статус задачи анализа изображения |
| `FeedbackStatus` | `pending`, `used` | Статус обработки фидбека |
| `sex` | `male`, `female` | Пол пользователя |
| `activity_level` | `sedentary`, `light`, `moderate`, `active`, `very_active` | Уровень физической активности |
| `goal` | `lose`, `maintain`, `gain` | Цель по весу: задаёт дефицит/профицит калорий и профиль БЖУ |
| `meal_type` | `breakfast`, `lunch`, `dinner`, `snacks` | Тип приёма пищи |
| `weight source` | `manual`, `registration`, `profile_edit` | Источник записи о взвешивании |
| `workout_type` | `strength`, `cardio`, `stretching`, `sport`, `other` | Тип тренировки |
| `protein_type` (Product) | `animal`, `plant`, `mixed` | Источник белка продукта (для авторазделения животный/растительный) |
| `photo_source` (вычисляемое) | `user`, `ai` | Откуда фото записи дневника: загружено вручную или взято из AI-анализа |

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
| `token_version` | int | по умолчанию `0`; инкремент при смене пароля мгновенно инвалидирует все ранее выданные JWT |
| `height_cm` | float | nullable |
| `sex` | string | nullable (`male`/`female`) |
| `birth_date` | date | nullable |
| `activity_level` | string | nullable |
| `goal` | string | nullable (`lose`/`maintain`/`gain`); `NULL` = поддержание |
| `goal_rate_kg_per_week` | float | nullable; желаемый темп (модуль, ≤1.5), `NULL` = дефолт для цели |
| `target_weight_kg` | float | nullable; желаемый вес — нужен только для прогноза сроков |
| `custom_calorie_target` | float | nullable; ручная норма калорий, `NULL` = авторасчёт |
| `custom_protein_g` | float | nullable; ручная норма белка |
| `custom_protein_animal_g` | float | nullable; ручное разделение нормы белка (животный) |
| `custom_protein_plant_g` | float | nullable; ручное разделение нормы белка (растительный) |
| `custom_fat_g` | float | nullable |
| `custom_carbs_g` | float | nullable |
| `custom_water_ml` | float | nullable; ручная норма воды |

**Связи:** `meals` (1:N, cascade, legacy), `tasks` (1:N), `daily_logs` (1:N, cascade),
`weight_records` (1:N, cascade), `water_logs` (1:N, cascade), `workouts` (1:N, cascade).
**Примечание:** текущий вес НЕ хранится в `users` — источник правды — последняя запись
`weight_records`. Любая из `custom_*` норм, если задана, переопределяет расчёт по формулам
(см. [бизнес-правила](business-rules.md)) везде: в дневнике, воде, советчике, тренировках.

---

### WeightRecord (`weight_records`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `weight_kg` | float | обязательный |
| `waist_cm` | float | nullable — обхват талии |
| `chest_cm` | float | nullable — обхват груди |
| `hips_cm` | float | nullable — обхват бёдер |
| `shoulders_cm` | float | nullable — обхват плеч |
| `recorded_on` | date | обязательный, server default `current_date()` |
| `note` | string | nullable |
| `source` | string | по умолчанию `manual` |
| `created_at` | datetime | server default `now()` |

**Ограничение целостности:** `UniqueConstraint(user_id, recorded_on)` — одна запись на
пользователя в день (защита от дублей через upsert). Обхваты хранятся в той же строке, что и
вес — один замер на (пользователь + дата); любой обхват можно оставить пустым.

---

### DailyLog (`daily_logs`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `date` | date | обязательный, индекс, server default `current_date()` |

**Связи:** `entries` (1:N → MealEntry, cascade). Создаётся лениво при первом приёме пищи за день.

---

### MealEntry (`meal_entries`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `daily_log_id` | int | FK → daily_logs.id, обязательный, индекс |
| `food_name` | string | обязательный |
| `calories` | float | обязательный |
| `protein_g` | float | обязательный |
| `protein_animal_g` | float | по умолчанию `0`; часть `protein_g`, животный белок |
| `protein_plant_g` | float | по умолчанию `0`; часть `protein_g`, растительный белок (сумма ≤ `protein_g`, остаток — «источник не определён») |
| `fat_g` | float | обязательный |
| `carbs_g` | float | обязательный |
| `weight_g` | float | обязательный |
| `meal_type` | string | по умолчанию `snacks` |
| `task_id` | string | FK → tasks.id, nullable (заполнен → запись создана/дополнена из AI-анализа) |
| `photo_path` | string | nullable — фото, добавленное пользователем вручную (путь на диске) |
| `created_at` | datetime | server default `now()` |

**Связи:** `items` (1:N → MealEntryItem, cascade) — блюда составного приёма («гарнир + основное
блюдо»); при наличии `items` поля `calories`/`protein_g`/... на самой записи — это суммы по
блюдам. Вычисляемые свойства модели: `photo_url` (подписанная ссылка `/uploads/...`, приоритет —
своё фото, затем фото AI-анализа) и `photo_source` (`user`/`ai`/`null`).

---

### MealEntryItem (`meal_entry_items`)

Блюдо внутри составного приёма пищи. Итоги по приёму хранятся и пересчитываются на `MealEntry`.

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `meal_entry_id` | int | FK → meal_entries.id, обязательный, индекс |
| `food_name` | string | обязательный |
| `weight_g`, `calories`, `protein_g`, `fat_g`, `carbs_g` | float | по умолчанию `0` |
| `protein_animal_g`, `protein_plant_g` | float | по умолчанию `0`; разделение белка блюда |
| `created_at` | datetime | server default `now()` |

---

### WaterLog (`water_logs`)

Выпитая вода за день, в миллилитрах.

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `date` | date | обязательный, индекс, server default `current_date()` |
| `total_ml` | float | по умолчанию `0` |
| `created_at` | datetime | server default `now()` |
| `updated_at` | datetime | onupdate `now()` |

**Ограничение целостности:** `UniqueConstraint(user_id, date)` — одна запись на пользователя в
день; фронт добавляет/убирает по одному стакану (`utils.GLASS_ML` = 250 мл), upsert без дублей.

---

### Workout (`workouts`)

Дневник тренировок (вкладка «Тренировки»).

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `date` | date | обязательный, индекс, server default `current_date()` |
| `workout_type` | string | по умолчанию `other` (`strength`/`cardio`/`stretching`/`sport`/`other`) |
| `title` | string | обязательный |
| `description` | text | nullable |
| `started_at` | string | nullable, формат `HH:MM` |
| `duration_min` | float | по умолчанию `0` |
| `calories_burned` | float | по умолчанию `0` |
| `created_at` | datetime | server default `now()` |

**Связи:** `items` (1:N → WorkoutItem, cascade) — упражнения внутри составной тренировки
(«жим лёжа 25 мин + становая 25 мин»); итоги (`duration_min`, `calories_burned`) хранятся на
`Workout` и пересчитываются при сохранении.

---

### WorkoutItem (`workout_items`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `workout_id` | int | FK → workouts.id, обязательный, индекс |
| `name` | string | обязательный |
| `duration_min`, `calories_burned` | float | по умолчанию `0` |
| `created_at` | datetime | server default `now()` |

---

### Exercise (`exercises`)

Справочник упражнений с примерным расходом калорий; используется формой записи тренировки для
авторасчёта.

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `name` | string | уникальный, обязательный, индекс |
| `category` | string | по умолчанию `other` (соответствует `workout_type`) |
| `kcal_per_min` | float | обязательный — ккал/мин для человека ~70 кг (оценка по MET) |
| `created_at` | datetime | server default `now()` |

Вычисляемое свойство `kcal_per_30min` — округлённое `kcal_per_min × 30` для UI («Жим лёжа · 30
мин ≈ 180 ккал»). Засевается идемпотентно при старте приложения (`seed_exercises.py`).

---

### Task (`tasks`)

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | string (UUID) | PK |
| `user_id` | int | FK → users.id, обязательный, индекс |
| `image_path` | string | обязательный (на диске; наружу — подписанный URL `/uploads/<file>?exp=&sig=`) |
| `status` | enum TaskStatus | по умолчанию `pending` |
| `result_json` | text | nullable (JSON результата анализа) |
| `error` | text | nullable |
| `image_hash` | string | nullable, индекс (для кэширования по хэшу изображения) |
| `created_at` | datetime | server default `now()` |
| `updated_at` | datetime | onupdate `now()` |

**Примечание:** свойство `result` модели возвращает `result_json`; схема `TaskResponse` парсит
его в объект результата анализа (см. ниже).

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

Справочник КБЖУ (нутриенты на 100 г), используется ML-сервисом и поиском продуктов.

| Поле | Тип | Ограничения |
|------|-----|------------|
| `id` | int | PK |
| `name` | string | уникальный, обязательный, индекс |
| `calories`, `protein`, `fat`, `carbs` | float | обязательные, на 100 г |
| `protein_type` | string | nullable, по умолчанию `mixed` (`animal`/`plant`/`mixed`) — проставляется классификатором `protein_source.classify` по названию при засеве |
| `created_at` | datetime | server default `now()` |

---

### Meal / MealItem / Photo (legacy)

Сущности `meals`, `meal_items`, `photos` присутствуют в модели данных (агрегаты приёмов
пищи и фото-вложения), но в текущем наборе REST-эндпоинтов напрямую не используются —
актуальный учёт ведётся через `DailyLog` + `MealEntry`(+ `MealEntryItem`). Учитывать при
проверке миграций БД; при написании автотестов эти таблицы можно игнорировать.

---

## Схемы обмена (Pydantic / контракты API)

### Аутентификация

**`AuthRequest`** (вход в `/login`, `/token`)
- `email`: email, опционально (обязателен при `grant_type=password`)
- `password`: string, опционально (обязателен при `grant_type=password`)
- `grant_type`: string, по умолчанию `password` (`password` | `refresh_token`)
- `refresh_token`: string, опционально (обязателен при `grant_type=refresh_token`)

**`Token`** (ответ)
- `access_token`: string, `refresh_token`: string | null, `token_type`: `bearer`

**`UserCreate`** (регистрация)
- `email`: email, обязательный; `full_name`: string | null
- `password`: string, **min_length=8**, обязательный
- `height_cm`, `weight_kg`: float, `0 < x < 300`, опционально
- `waist_cm`, `chest_cm`, `hips_cm`, `shoulders_cm`: float, опционально — если `weight_kg` задан, все они попадают в первую запись истории взвешиваний (`source=registration`)

**`User`** (ответ) — `id`, `email`, `full_name`, `is_active`, `created_at`

**`ChangePasswordRequest`** — `current_password`, `new_password` (различаются, иначе `400`)

---

### Профиль и вес

**`ProfileUpdate`** (PUT профиля) — все поля опциональны: `full_name`, `height_cm`, `weight_kg`,
`sex`, `birth_date`, `activity_level`, `save_weight_as_record` (bool, по умолчанию `true`),
цель `goal` / `goal_rate_kg_per_week` (0…1.5) / `target_weight_kg`, плюс
ручные нормы `custom_calorie_target`, `custom_protein_g`, `custom_protein_animal_g`,
`custom_protein_plant_g`, `custom_fat_g`, `custom_carbs_g`, `custom_water_ml`.
Для `goal_rate_kg_per_week`, `target_weight_kg` и всех `custom_*` действует соглашение:
`null` = не менять, `0` = вернуть значение по умолчанию, `>0` = установить.

**`ProfileResponse`** — `id`, `email`, `full_name`, `height_cm`, `current_weight_kg`,
`current_waist_cm`/`current_chest_cm`/`current_hips_cm`/`current_shoulders_cm`, `sex`,
`birth_date`, `activity_level`, `recent_weights` (последние ~30 `WeightRecordResponse`), `bmr`,
`bmi`, `maintenance_calories` (норма поддержания, база для цели),
`daily_calorie_target`, `protein_target_g`, `protein_animal_target_g`, `protein_plant_target_g`,
`fat_target_g`, `carbs_target_g`, `water_target_ml`, цель `goal` / `goal_rate_kg_per_week` /
`target_weight_kg` и её план `goal_plan`, список `calc_warnings`, плюс эхо всех `custom_*` полей
(что задано вручную — для формы «Мои нормы»).

**`GoalPlanResponse`** (`ProfileResponse.goal_plan`) — `goal`, `requested_rate_kg_per_week`,
`applied_rate_kg_per_week` (после ограничителей безопасности), `target_weight_kg`,
`calorie_delta` (<0 дефицит, >0 профицит), `calorie_delta_pct`, `remaining_kg`,
`weeks_to_goal`, `eta_date`, `reached`. См. [BR-03A](business-rules.md).

**`CalcWarning`** (`ProfileResponse.calc_warnings[]`) — `code`, `message`. Коды: `rate_capped`,
`deficit_capped`, `surplus_capped`, `below_bmr`, `absolute_floor`, `goal_reached`,
`target_conflicts_goal`, `missing_data`.

**`WeightRecordCreate`** — `weight_kg` (`0<x<300`, обязательный), `recorded_on` (опц., по
умолчанию сегодня, не может быть в будущем), `note` (опц., ≤200 симв.), `waist_cm`/`chest_cm`/
`hips_cm`/`shoulders_cm` (опц.).

**`WeightRecordUpdate`** — те же поля, все опциональны (частичное редактирование по `id`).

**`WeightRecordResponse`** — `id`, `weight_kg`, обхваты, `recorded_on`, `note`|null, `source`.

---

### Продукты и штрих-коды

**`ProductResponse`** — `id`, `name`, `calories`, `protein`, `fat`, `carbs` (на 100 г),
`protein_type`.

**`BarcodeProductResponse`** — данные продукта из Open Food Facts, приведённые к тому же виду
КБЖУ на 100 г, плюс исходный штрих-код.

---

### Анализ и задачи

**`AiLimitResponse`** — сколько AI-анализов осталось сегодня (из дневного лимита, см. NFR).

**`TaskCreatedResponse`** (ответ `/analyze`) — `id`: string, `status`: string.

**`NutritionResponse`** (результат анализа внутри задачи) — `food` (обязательный), `weight_g`
(`0.1–5000`), `calories` (`0–10000`), `protein_g`, `fat_g`, `carbs_g` (`≥0`), `protein_animal_g`,
`protein_plant_g`, `confidence` (`0–1`), `note`|null, `ingredients`: список `IngredientResponse`,
плюс метаданные `source` (какой провайдер/кэш/фолбэк ответил), `models_tried`,
`processing_time_sec`.

**`IngredientResponse`** — `name`, `type` (`protein`|`carb`|`fat`|`vegetable`|`unknown`),
`weight_g`, `protein_type`.

**`TaskResponse`** — `id`, `status`, `result`: `NutritionResponse`|null, `image_path`|null
(отдаётся как подписанный URL `/uploads/<file>?exp=&sig=`), `error`|null, `created_at`,
`updated_at`|null.

---

### Дневник питания

**`MealEntryCreate`** — `food_name`, `calories`/`protein_g`/`fat_g`/`carbs_g` (`≥0`), `weight_g`
(`>0`), `protein_animal_g`/`protein_plant_g` (опц.), `meal_type` (по умолчанию `snacks`), `date`
(опц., по умолчанию сегодня), `task_id` (опц.), `items` (опц. список `MealItemBase` для
составного приёма — при наличии итоги пересчитываются на бэкенде из суммы блюд).

**`MealEntryResponse`** — `id`, `food_name`, КБЖУ (общие и разделение белка), `weight_g`,
`meal_type`, `created_at`, `task_id`|null, `items`: список `MealEntryItemResponse`, `photo_url`|
null, `photo_source`|null (`user`/`ai`).

**`AnalysisMealRequest`** (`/meals/from-analysis`) — `task_id` (обязательный), `meal_type` (по
умолчанию `snacks`).

**`DailyLogResponse`** — `date`, суммарные КБЖУ дня (общие + разделение белка), `meals`: список
`MealEntryResponse` (отсортированы: завтрак→обед→ужин, перекусы — по времени создания), `targets`:
нормы КБЖУ (с разделением белка), `water`: `WaterResponse`.

---

### Вода

**`WaterUpdate`** — `amount_ml` (опц.; без тела = +1 стакан 250 мл, отрицательное — убрать),
`date` (опц., не может быть в будущем).

**`WaterResponse`** — `date`, `total_ml`, `goal_ml`|null, `glass_ml` (250).

---

### Тренировки

**`WorkoutCreate`** — `workout_type` (по умолчанию `other`), `title` (обязательный),
`description` (опц.), `started_at` (опц., `HH:MM`), `duration_min`/`calories_burned` (опц. на
верхнем уровне, пересчитываются при наличии `items`), `date` (опц., не в будущем), `items` (опц.
список `WorkoutItemCreate` для составной тренировки).

**`WorkoutResponse`** — все поля `Workout` + `items`: список `WorkoutItemResponse`.

**`WorkoutsResponse`** (`GET /workouts`) — `date`, `workouts`: список `WorkoutResponse`,
`summary`: `WorkoutDaySummary` (`total_calories_burned`, `total_duration_min`, `count`,
`base_calorie_target`, `adjusted_calorie_target` — суточная норма + сожжённые калории), `week`:
список `WorkoutWeekDay` (`date`, `has_workout`) для недельной полоски активности.

**`ExerciseResponse`** — `id`, `name`, `category`, `kcal_per_min`, `kcal_per_30min`.

---

### AI-советчик

**`AdvisorResponse`** (`GET /advisor`) — `headline_title`, `headline_text`, `nutrition`: список
`AdvisorTip`, `training`: список `AdvisorTip` — советы дня, LLM или правила-фолбэк.

**`AdvisorAskRequest`** — `question`: string.
**`AdvisorAskResponse`** — `answer`: string (≤2000 симв.).

---

### Обратная связь

**`FeedbackRequest`** — `task_id` (обязательный), `correct_food` (**1..200 символов**),
`correct_weight` (int, **`0 < x ≤ 10000`**).

**`FeedbackResponse`** — `status`, `id`.

**`FeedbackListItem`** (админка) — `id`, `task_id`, `image_path`, `predicted_result` (object|
null), `corrected_food`, `corrected_weight`, `user_id`|null, `created_at`, `status`.

---

## Связанные документы

- [Функциональные требования](functional-requirements.md)
- [Бизнес-правила](business-rules.md)
- [Сводка эндпоинтов](../api/api-endpoints-summary.md)
- [OpenAPI спецификация](../api/swagger.yaml) — статическая копия контракта; актуальная
  машиночитаемая схема всегда доступна и на живом сервере по `/openapi.json`
