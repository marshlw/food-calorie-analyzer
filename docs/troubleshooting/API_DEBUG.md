# API & Frontend Integration - Troubleshooting Guide

## Проблемы и Решения

### 1. Ошибка 400 и Network Error при авторизации

**Причины:**
- Неправильный URL API
- CORS блокирует запросы
- Неправильный формат данных
- Серверные ошибки парсинга

**Решение:**

1. **Проверьте API URL в frontend:**
   ```bash
   # Откройте console в браузере (F12)
   # Должно вывести:
   # API Base URL: http://localhost:8000
   ```

2. **Проверьте .env.local:**
   ```env
   VITE_API_URL=http://localhost:8000
   ```

3. **Проверьте CORS конфиг в backend:**
   - ALLOWED_ORIGINS включает `http://localhost:5173` и `http://localhost:8000`
   - allow_methods включает все необходимые методы: GET, POST, PATCH, DELETE, OPTIONS

4. **Проверьте логи backend:**
   ```bash
   docker-compose logs api
   # Ищите Auth request content-type и body
   ```

### 2. Network Error - Сервер не отвечает

**Проверяем подключение:**

```bash
# 1. API запущен?
curl -v http://localhost:8000/health

# 2. Регистрация работает?
curl -X POST http://localhost:8000/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","full_name":"Test"}'

# 3. Логин работает?
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123","grant_type":"password"}'
```

### 3. Ошибка парсинга JSON

**Frontend отправляет правильный JSON, но backend не парсит.**

Проверьте headers:
```javascript
// В консоли браузера (Network tab)
// Request Headers должны содержать:
// Content-Type: application/json
// Authorization: Bearer {token}
```

### 4. CORS ошибка: "Access to XMLHttpRequest blocked by CORS policy"

**Решение:**

1. Убедитесь что backend запущен на `http://localhost:8000`
2. Frontend на `http://localhost:5173` (Vite dev server)
3. Проверьте CORS middleware в backend:
   ```python
   app.add_middleware(
       CORSMiddleware,
       allow_origins=["http://localhost:5173", ...],
       allow_credentials=True,
       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
       allow_headers=["*"],
   )
   ```

### 5. 401 Unauthorized при обращении к защищенным эндпоинтам

**Проверьте:**

1. Токен сохраняется в localStorage:
   ```javascript
   localStorage.getItem('access_token')
   localStorage.getItem('refresh_token')
   ```

2. Токен отправляется в заголовке:
   ```
   Authorization: Bearer {token}
   ```

3. Токен действительный (не истек - 30 минут)

## Запуск и Тестирование

### Локальная разработка

```bash
# Terminal 1: Backend
cd ai-healthy
docker-compose up -d db redis

# Или если используете локальный python
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
# Откройте http://localhost:5173
```

### Docker compose

```bash
# Полный стек
docker-compose up -d

# Проверить статус
docker-compose ps

# Логи
docker-compose logs -f api
docker-compose logs -f db
```

## API Endpoints

### Auth
- **POST** `/api/v1/register` - Регистрация
- **POST** `/api/v1/login` - Логин (grant_type: password)
- **POST** `/api/v1/token` - Обновление токена (grant_type: refresh_token)
- **GET** `/api/v1/me` - Текущий пользователь (требует auth)

### Meals (все требуют auth)
- **POST** `/api/v1/meals` - Добавить прием
- **PATCH** `/api/v1/meals/{id}` - Редактировать
- **DELETE** `/api/v1/meals/{id}` - Удалить
- **GET** `/api/v1/daily-log` - Дневник за день
- **POST** `/api/v1/meals/from-analysis` - Добавить из анализа

### Tasks (все требуют auth)
- **POST** `/api/v1/analyze` - Загрузить фото на анализ
- **GET** `/api/v1/task/{id}` - Статус анализа
- **GET** `/api/v1/tasks` - История анализов
- **POST** `/api/v1/feedback` - Отправить исправление

## Пример Curl команд

### Регистрация
```bash
curl -X POST http://localhost:8000/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "full_name": "John Doe"
  }'
```

### Логин
```bash
curl -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "securepass123",
    "grant_type": "password"
  }' | jq .
```

**Ответ:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### Получить профиль (с токеном)
```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

curl -X GET http://localhost:8000/api/v1/me \
  -H "Authorization: Bearer $TOKEN"
```

### Добавить прием пищи
```bash
TOKEN="eyJ0eXAiOiJKV1QiLCJhbGc..."

curl -X POST http://localhost:8000/api/v1/meals \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "food_name": "куриное филе с рисом",
    "calories": 350,
    "protein_g": 35,
    "fat_g": 8,
    "carbs_g": 35,
    "weight_g": 200,
    "meal_type": "lunch"
  }'
```

## Отладка в Browser DevTools

1. **Откройте Developer Tools** (F12)
2. **Network tab:**
   - Фильтруйте по `Fetch/XHR`
   - Посмотрите запрос и ответ
   - Проверьте headers и body
   - Проверьте статус code

3. **Console tab:**
   - Проверьте логи (API Base URL, Request/Response)
   - Ищите ошибки

4. **Storage tab:**
   - Проверьте localStorage
   - Ищите `access_token` и `refresh_token`

## Common Status Codes

- **200** - OK
- **201** - Created
- **400** - Bad Request (ошибка в формате данных)
- **401** - Unauthorized (токен не валидный или истек)
- **404** - Not Found (ресурс не найден)
- **500** - Internal Server Error (ошибка сервера)

## Переменные окружения

### Backend (.env)
```env
DATABASE_URL=postgresql://ai_healthy:password@localhost:5432/ai_healthy
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=your-secret-key-here
ALLOWED_ORIGINS=["http://localhost:5173", "http://localhost:8000"]
```

### Frontend (.env.local)
```env
VITE_API_URL=http://localhost:8000
```

## Помощь

Если проблема сохраняется:

1. Проверьте все логи:
   ```bash
   docker-compose logs api
   docker-compose logs db
   docker-compose logs redis
   ```

2. Перезагрузитесь:
   ```bash
   docker-compose restart api
   # или
   docker-compose down && docker-compose up
   ```

3. Очистите браузер:
   - F12 → Storage → Clear Site Data
   - Refresh страницу

4. Проверьте подключение к DB:
   ```bash
   docker-compose exec api python -c "from app.database import engine; print(engine)"
   ```
