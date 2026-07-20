# AI-Healthy API - Postman Collection

Полная коллекция API запросов для приложения AI-Healthy (Здоровое питание): **40 запросов**
в 11 папках, соответствует текущему `app/main.py`.

## 📦 Файл

Коллекция находится здесь же, в `docs/api/`:

- **[postman-collection.json](postman-collection.json)** — коллекция Postman v2.1 (запросы + тестовые
  скрипты + переменные окружения внутри самой коллекции — отдельный файл `*.postman_environment.json`
  не нужен). Это единственная поддерживаемая коллекция проекта; более старый дубликат в корне
  репозитория (`AI-Healthy-API-Collection.postman_collection.json` +
  `AI-Healthy-Environment.postman_environment.json`, 17 запросов, часть контрактов уже не
  совпадает с кодом) удалён как устаревший.

## 🚀 Быстрый старт

### 1. Импортируем коллекцию в Postman

- Откройте **Postman**
- Нажмите **Import** → **File**
- Выберите `docs/api/postman-collection.json`
- Нажмите **Import**

### 2. Задаём переменные коллекции

Переменные уже объявлены внутри коллекции (вкладка **Variables** после импорта) — просто
подставьте свои значения:

| Переменная | Описание | Значение по умолчанию |
|----------|---------|--------|
| `base_url` | URL базового API | `http://localhost:8000` |
| `email` | Email тестового пользователя | `qa_user@example.com` |
| `password` | Пароль тестового пользователя | `password123` |
| `access_token` | JWT токен доступа | заполняется автоматически после `Login`/`Token` |
| `refresh_token` | Токен для обновления доступа | заполняется автоматически |
| `admin_token` | Значение `X-Admin-Token` для admin-эндпоинтов | `change-me-in-production` — замените на реальный `ADMIN_TOKEN` из `.env` |
| `task_id` | ID задачи анализа | заполняется автоматически после `Analyze Image` |
| `meal_id` | ID записи о приёме пищи | заполняется автоматически после `Add Meal` |
| `feedback_id` | ID обратной связи | заполняется автоматически после `Submit Feedback` |
| `workout_id` | ID тренировки | заполняется автоматически после `Add Workout` |
| `barcode` | Тестовый штрих-код для `Get Product By Barcode` | `4600494001313` |

Авторизация коллекции по умолчанию — `Bearer {{access_token}}` (наследуется всеми запросами,
кроме явно помеченных `noauth`: регистрация/логин/health/admin-эндпоинты используют
`X-Admin-Token` вместо Bearer).

## 📋 Папки и эндпоинты

### 🏥 System
- `GET /health` — проверка статуса API

### 🔐 Authentication
- `POST /api/v1/register` — регистрация
- `POST /api/v1/login` — вход (access/refresh токены)
- `POST /api/v1/token` — `grant_type=password` или `refresh_token`
- `GET /api/v1/me` — текущий пользователь
- `POST /api/v1/change-password` — смена пароля (инвалидирует все ранее выданные токены)

### 👤 Profile
- `GET /api/v1/profile` — профиль, BMR, нормы КБЖУ/воды, последние взвешивания
- `PUT /api/v1/profile` — обновление профиля
- `POST /api/v1/profile/weight` — добавить/обновить запись веса (upsert по дате)
- `GET /api/v1/profile/weight-history` — история взвешиваний

### 📸 Analysis (анализ фото)
- `GET /api/v1/analyze/limit` — остаток дневного лимита AI-анализов
- `POST /api/v1/analyze` — загрузить и поставить фото в очередь на анализ
- `GET /api/v1/task/{task_id}` — статус/результат анализа
- `GET /api/v1/tasks` — история анализов пользователя

### 🍽️ Diary (дневник питания)
- `POST /api/v1/meals` — добавить приём пищи вручную
- `POST /api/v1/meals/from-analysis` — создать приём пищи из результата анализа
- `GET /api/v1/daily-log` — дневной лог питания
- `PATCH /api/v1/meals/{meal_id}` — обновить приём пищи
- `POST /api/v1/meals/{meal_id}/photo` — прикрепить/заменить фото записи
- `DELETE /api/v1/meals/{meal_id}/photo` — удалить своё фото записи
- `DELETE /api/v1/meals/{meal_id}` — удалить приём пищи

### 💧 Water (вода)
- `GET /api/v1/water` — выпито за день + норма
- `POST /api/v1/water` — добавить стакан / произвольный объём / убрать (отрицательный `amount_ml`)

### 🛒 Products & Barcode
- `GET /api/v1/products` — поиск продукта по названию (справочник КБЖУ)
- `POST /api/v1/barcode/scan` — сканирование штрих-кода по фото (Open Food Facts)
- `GET /api/v1/barcode/{code}` — поиск продукта по известному штрих-коду

### 🏋️ Workouts (тренировки)
- `GET /api/v1/workouts` — тренировки за день + сводка + недельная активность
- `POST /api/v1/workouts` — добавить тренировку
- `PUT /api/v1/workouts/{workout_id}` — редактировать
- `DELETE /api/v1/workouts/{workout_id}` — удалить
- `GET /api/v1/exercises` — справочник упражнений (ккал/мин)

### ✦ Advisor (AI-советчик)
- `GET /api/v1/advisor` — советы дня (LLM с фолбэком на правила)
- `POST /api/v1/advisor/ask` — свободный вопрос советчику

### 💬 Feedback
- `POST /api/v1/feedback` — отправить коррекцию анализа

### 🔧 Admin
- `GET /api/v1/admin/feedback` — список фидбеков
- `GET /api/v1/admin/feedback/{feedback_id}` — один фидбек
- `PATCH /api/v1/admin/feedback/{feedback_id}/status` — изменить статус

## 📝 Типовой сценарий (Workflow)

```
1. Health Check        GET /health                    → ✅ status: "ok"
2. Register             POST /api/v1/register           → ✅ пользователь создан
3. Login                POST /api/v1/login               → ✅ access_token/refresh_token сохранены
4. Get Profile           GET /api/v1/profile              → ✅ нормы КБЖУ/воды
5. Analyze Image         POST /api/v1/analyze (файл)       → ✅ task_id
6. Get Task              GET /api/v1/task/{task_id}         → ✅ результат, когда status=success
7. Add Meal From Analysis POST /api/v1/meals/from-analysis  → ✅ запись дневника создана
8. Get Daily Log         GET /api/v1/daily-log             → ✅ сводка дня
9. Add Workout           POST /api/v1/workouts             → ✅ тренировка записана
10. Get Advisor Tips      GET /api/v1/advisor               → ✅ советы дня
11. Submit Feedback       POST /api/v1/feedback             → ✅ фидбек зафиксирован
```

## 🛠️ Советы для тестирования

### Автоматическое сохранение токенов и id
Тестовые скрипты (**Tests**) уже настроены в `Login`, `Token`, `Change Password`, `Analyze Image`,
`Add Meal`, `Add Workout` и `Submit Feedback` — они сами кладут `access_token`, `refresh_token`,
`task_id`, `meal_id`, `workout_id`, `feedback_id` в переменные коллекции.

### Работа с файлами
Для `Analyze Image`, `Upload Meal Photo`, `Scan Barcode` используется `form-data` — выберите
файл через File picker в поле `file`.

### Отладка ошибок
1. Проверьте, что `base_url` соответствует вашему хосту (по умолчанию `http://localhost:8000`).
2. Убедитесь, что `access_token` не пуст/не истёк для защищённых эндпоинтов (access-токен живёт
   30 минут — прогоните `Token - Refresh Grant`, если истёк).
3. Для admin-эндпоинтов проверьте заголовок `X-Admin-Token` — сервер отключает эти ручки (404),
   если `ADMIN_TOKEN` не задан в `.env` или оставлен значением по умолчанию.
4. Смотрите тело ответа — API возвращает `{"detail": "..."}"` с описанием ошибки.

## 🔒 Безопасность

- Меняйте `admin_token`/`password` перед использованием в реальном окружении.
- Никогда не коммитьте реальные токены/пароли в git.
- Используйте HTTPS в продакшене.

## 📱 Поддерживаемые форматы изображений

JPEG / JPG / PNG / WEBP, максимальный размер — 10 МБ.

## 🚨 Коды ошибок

| Код | Описание |
|-----|---------|
| 200 | OK |
| 201 | Created |
| 204 | No Content (например, удаление записи веса) |
| 400 | Bad Request — неверные данные / дата в будущем / неподдерживаемый тип файла |
| 401 | Unauthorized — нет/невалиден/просрочен токен, неверные учётные данные |
| 403 | Forbidden — неверный `X-Admin-Token` |
| 404 | Not Found — ресурс не найден или принадлежит другому пользователю |
| 409 | Conflict — дубликат записи (например, вес на уже занятую дату) |
| 413 | Payload Too Large — файл больше 10 МБ |
| 422 | Unprocessable Entity — ошибка валидации тела/параметров |
| 500 | Internal Server Error |

## 📞 Поддержка

Статическая копия OpenAPI-спецификации — [swagger.yaml](swagger.yaml). Актуальная
машиночитаемая схема также доступна на живом сервере по `/openapi.json`, интерактивный
Swagger UI — по `/docs` (оба доступны только при `ENABLE_DOCS=true` в конфиге; в проде выключены
из соображений безопасности). См. также [сводку эндпоинтов](api-endpoints-summary.md).
