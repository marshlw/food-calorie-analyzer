# Исправления: API & Frontend Integration

> Исторический журнал исправлений — оставлен как есть. Текущее состояние CORS/конфига описано в
> [architecture.md](../architecture/architecture.md#configuration-appconfigpy).

## 🔧 Что было исправлено

### Backend (app/main.py)

1. **CORS методы** - добавлены `DELETE` методы
   ```python
   allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
   ```

2. **Функция `_get_auth_request`** - улучшена обработка ошибок
   - Добавлено логирование для отладки
   - Добавлена fallback логика (если form парсинг не работает, пробуем JSON)
   - Улучшена обработка исключений с понятными сообщениями

3. **Логирование** - добавлено логирование запросов и ошибок

### Backend (app/config.py)

1. **CORS origins** - расширен список разрешенных источников
   ```python
   ALLOWED_ORIGINS = [
       "http://localhost",
       "http://localhost:3000",      # Next.js
       "http://localhost:5173",      # Vite dev server
       "http://localhost:8000",      # API
       "http://127.0.0.1",
       "http://127.0.0.1:3000",
       "http://127.0.0.1:5173",
       "http://127.0.0.1:8000",
       "http://0.0.0.0:8000",        # Docker
   ]
   ```

### Frontend (src/api/axios.ts)

1. **Логирование запросов** - добавлено детальное логирование
   - API Base URL на старте
   - Все запросы с параметрами
   - Все ответы со статусом
   - Все ошибки с деталями

2. **Content-Type header** - явно установлен
   ```typescript
   headers: {
       'Content-Type': 'application/json',
   }
   ```

3. **Улучшена обработка ошибок** - детальное логирование для отладки

### Frontend (.env.local)

Создан файл конфигурации:
```env
VITE_API_URL=http://localhost:8000
```

## 🚀 Как Использовать

### 1. Локальная разработка

```bash
# Terminal 1: Backend
cd ai-healthy
# Option A: Docker compose
docker-compose up -d db redis
docker-compose up -d api

# Option B: Локально
pip install -r requirements.txt
python -m uvicorn app.main:app --reload

# Terminal 2: Frontend
cd frontend
npm run dev
# Откройте http://localhost:5173
```

### 2. Docker Compose (все сразу)

```bash
docker-compose up -d
# API на http://localhost:8000
# Frontend на http://localhost:8000 (сервируется статически)
# или http://localhost:5173 (если dev server)
```

### 3. Тестирование API

```bash
# Bash скрипт (Linux/Mac)
bash test-api.sh

# Или вручную - примеры в API_DEBUG.md
curl -X POST http://localhost:8000/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'
```

## 📊 Отладка ошибок 400 и Network Error

Откройте **Browser DevTools** (F12):

1. **Network tab:**
   - Фильтруйте по `Fetch/XHR`
   - Посмотрите на запрос (метод, URL, headers, body)
   - Посмотрите на ответ (статус, headers, body)

2. **Console tab:**
   - Ищите логи "API Base URL: ..."
   - Ищите "Request:" и "Response:" логи
   - Ищите ошибки красного цвета

3. **Storage tab:**
   - Проверьте, что токены сохраняются
   - localStorage должен содержать access_token и refresh_token

## 🔍 Что Проверить Если Не Работает

1. **Frontend URL:**
   ```javascript
   // Console
   console.log(import.meta.env.VITE_API_URL)
   // Должен быть: http://localhost:8000
   ```

2. **Backend запущен:**
   ```bash
   curl http://localhost:8000/health
   # Должен вернуть 200 OK
   ```

3. **CORS разрешен:**
   - Проверьте `app.config.py` - есть ли ваш origin?
   - Проверьте Network tab - есть ли `Access-Control-*` headers?

4. **Логи backend:**
   ```bash
   docker-compose logs api
   # Ищите "Auth request" и "Response error"
   ```

5. **Логи frontend:**
   ```javascript
   // F12 Console
   // Ищите "API Base URL: http://localhost:8000"
   // Ищите "Request:" и "Response:" логи
   ```

## 📁 Файлы для Отладки

- **API_DEBUG.md** - подробная инструкция по отладке
- **test-api.sh** - скрипт для тестирования всех endpoints
- **frontend/.env.local** - конфигурация для development

## ✅ Проверочный Список

- [ ] Backend запущен на http://localhost:8000
- [ ] Frontend запущен на http://localhost:5173 или http://localhost:8000
- [ ] `.env.local` содержит `VITE_API_URL=http://localhost:8000`
- [ ] DB миграции применены
- [ ] Redis запущен
- [ ] CORS origins включают ваш frontend URL
- [ ] В Network tab видны запросы с правильными headers
- [ ] Логи показывают "Request:" и "Response:" сообщения
- [ ] localStorage содержит `access_token` после логина
- [ ] Авторизация работает (можете залогиниться)

## 📚 Дополнительно

- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [Axios Configuration](https://axios-http.com/docs/req_config)
- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode)
- [Browser DevTools Guide](https://developer.chrome.com/docs/devtools/)
