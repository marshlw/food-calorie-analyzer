# AI-Healthy API - Postman Collection

Полная коллекция API запросов для приложения AI-Healthy (Здоровое питание).

## 📦 Файлы

Файлы коллекции находятся в **корне проекта**:

1. **AI-Healthy-API-Collection.postman_collection.json** - Основная коллекция с 17 API endpoints
2. **AI-Healthy-Environment.postman_environment.json** - Файл окружения с переменными

## 🚀 Быстрый старт

### 1. Импортируем коллекцию в Postman

- Откройте **Postman**
- Нажмите **Import** → **File**
- Выберите `AI-Healthy-API-Collection.postman_collection.json`
- Нажмите **Import**

### 2. Импортируем окружение

- Нажмите **Import** → **File**
- Выберите `AI-Healthy-Environment.postman_environment.json`
- В левом верхнем углу выберите это окружение из выпадающего списка

## 📋 API Endpoints

### 🏥 Health
- `GET /health` - Проверка статуса API

### 🔐 Authentication (Аутентификация)
- `POST /api/v1/register` - Регистрация нового пользователя
- `POST /api/v1/login` - Вход (получение access_token и refresh_token)
- `POST /api/v1/token` - Обновление access_token используя refresh_token
- `GET /api/v1/me` - Получить данные текущего пользователя

### 📸 Image Analysis (Анализ фото)
- `POST /api/v1/analyze` - Загрузить и проанализировать фото еды
- `GET /api/v1/task/{task_id}` - Получить статус и результаты анализа
- `GET /api/v1/tasks` - Получить историю всех анализов пользователя

### 🍽️ Meals (Прием пищи)
- `POST /api/v1/meals` - Добавить прием пищи вручную
- `POST /api/v1/meals/from-analysis` - Создать прием пищи из результатов анализа
- `GET /api/v1/daily-log` - Получить дневной лог питания
- `PATCH /api/v1/meals/{meal_id}` - Обновить прием пищи
- `DELETE /api/v1/meals/{meal_id}` - Удалить прием пищи

### 💬 Feedback (Обратная связь)
- `POST /api/v1/feedback` - Отправить коррекцию анализа для улучшения модели

### 🔧 Admin (Администратор)
- `GET /api/v1/admin/feedback` - Получить все отправки обратной связи
- `GET /api/v1/admin/feedback/{feedback_id}` - Получить детали обратной связи
- `PATCH /api/v1/admin/feedback/{feedback_id}/status` - Обновить статус обратной связи

## 🔑 Переменные Окружения

| Переменная | Описание | Пример |
|----------|---------|--------|
| `base_url` | URL базового API | `http://localhost:8000` |
| `access_token` | JWT токен доступа | Устанавливается после логина |
| `refresh_token` | Токен для обновления доступа | Устанавливается после логина |
| `admin_token` | Токен администратора | `change-me-in-production` |
| `task_id` | ID задачи анализа | Устанавливается после анализа |
| `meal_id` | ID записи о приеме пищи | Получается из GET /meals |
| `feedback_id` | ID обратной связи | Получается из GET /admin/feedback |

## 📝 Примеры Использования

### 1. Регистрация и Логин

```
1. POST /api/v1/register
   - Заполнить email, password, full_name
   
2. POST /api/v1/login
   - Использовать те же email и password
   - ✅ Postman автоматически сохранит access_token и refresh_token
```

### 2. Анализ фото еды

```
1. POST /api/v1/analyze
   - Выбрать файл изображения
   - Используется Bearer token из headers
   - Получаем task_id в ответе
   
2. GET /api/v1/task/{task_id}
   - Проверить статус анализа (PENDING, SUCCESS, FAILURE)
   - Когда статус SUCCESS, получаем результаты анализа
```

### 3. Добавление приема пищи

```
1. Вариант A: Ручное добавление
   POST /api/v1/meals
   - Передать food_name, calories, protein_g, fat_g, carbs_g, weight_g, meal_type
   
2. Вариант B: Из результатов анализа
   POST /api/v1/meals/from-analysis
   - Передать task_id и meal_type
   - Данные о питательности возьмутся из результатов анализа
```

### 4. Получение дневного лога

```
GET /api/v1/daily-log?date_str=2024-05-25
- Получить полный дневной лог с суммарными калориями, белками, жирами, углеводами
```

## 🛠️ Советы для тестирования

### Автоматическое сохранение токенов
Вы можете настроить **Tests** в requests для автоматического сохранения токенов:

```javascript
// Для login/token endpoints:
var jsonData = pm.response.json();
pm.environment.set("access_token", jsonData.access_token);
pm.environment.set("refresh_token", jsonData.refresh_token);
```

### Работа с файлами
При загрузке изображения используйте `form-data` и выберите файл через кнопку File picker.

### Отладка ошибок
1. Проверьте **base_url** соответствует вашему хосту
2. Убедитесь в наличии Bearer token для защищенных endpoints
3. Проверьте **X-Admin-Token** header для админ endpoints
4. Смотрите ответ (Response) для деталей ошибки

## 🔄 Workflow Пример

```
1. Health Check
   GET /health → ✅ status: "ok"

2. Register
   POST /api/v1/register → ✅ User created

3. Login
   POST /api/v1/login → ✅ Got access_token

4. Get Current User
   GET /api/v1/me → ✅ User data

5. Analyze Food
   POST /api/v1/analyze (upload image) → ✅ task_id

6. Check Analysis Status
   GET /api/v1/task/{task_id} → ✅ Results when ready

7. Add Meal from Analysis
   POST /api/v1/meals/from-analysis → ✅ Meal created

8. View Daily Log
   GET /api/v1/daily-log → ✅ Daily nutrition summary

9. Submit Feedback
   POST /api/v1/feedback → ✅ Feedback recorded
```

## 🔒 Безопасность

- Меняйте `admin_token` в продакшене
- Никогда не коммитьте реальные токены в git
- Используйте HTTPS в продакшене
- Используйте переменные окружения для чувствительных данных

## 📱 Поддерживаемые форматы изображений

- JPEG / JPG
- PNG
- WEBP

Максимальный размер: 10 MB

## 🚨 Коды Ошибок

| Код | Описание |
|-----|---------|
| 200 | OK - Запрос успешен |
| 201 | Created - Ресурс создан |
| 400 | Bad Request - Неверные данные |
| 401 | Unauthorized - Требуется аутентификация |
| 403 | Forbidden - Доступ запрещен |
| 404 | Not Found - Ресурс не найден |
| 413 | Payload Too Large - Файл слишком большой |
| 500 | Internal Server Error - Ошибка сервера |

## 📞 Поддержка

Для вопросов о API смотрите документацию в `/docs/` или используйте Swagger UI на `/docs` после запуска сервера.
