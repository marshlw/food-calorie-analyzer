# Docker Setup для AI Healthy

> **Статус на момент последнего обновления этого файла:** `Dockerfile` и `requirements.txt` есть
> в корне репозитория и соответствуют описанию ниже — `docker build -t ai-healthy:latest .`
> должен работать как есть. Чего нет — `docker-compose.yml` и `docker-compose-prod.yml`
> (проверено — см. [аудит кода](../architecture/code_audit.md)): команды `docker-compose ...`
> ниже не заработают, пока эти файлы не будут добавлены. До этого — либо поднимайте контейнеры
> вручную (`docker run`, с внешними PostgreSQL/Redis), либо запускайте проект локально без
> Docker (раздел [«Локальный запуск без Docker»](#локальный-запуск-без-docker) ниже работает
> уже сейчас).

## Требования

- Docker 20.10+
- Docker Compose 2.0+

## Структура

Dockerfile использует **multi-stage build**:

1. **Stage 1 (frontend-builder)**: Node.js 18-alpine
   - Устанавливает зависимости из `frontend/package.json`
   - Собирает frontend: `npm run build`
   - Результат: `dist/` папка с готовыми файлами

2. **Stage 2 (production)**: Python 3.10-slim
   - Устанавливает Python зависимости
   - Копирует backend
   - Копирует собранный frontend из Stage 1 в `app/static/frontend`
   - FastAPI сервирует frontend как статические файлы

## Сборка

### Локальная разработка (с docker-compose.yml)

```bash
# Запуск всех сервисов (БД, Redis, API, Celery, Frontend dev)
docker-compose up -d

# Логи
docker-compose logs -f api

# Остановка
docker-compose down
```

### Production (с docker-compose-prod.yml)

```bash
# Сборка и запуск
docker-compose -f docker-compose-prod.yml up -d

# Просмотр сборки
docker-compose -f docker-compose-prod.yml build --no-cache
```

## Только Docker (без Compose)

### Сборка образа

```bash
docker build -t ai-healthy:latest .
```

### Запуск контейнера

```bash
docker run -d \
  --name ai-healthy \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql://user:password@db:5432/ai_healthy" \
  -e REDIS_URL="redis://redis:6379/0" \
  -v ./uploads:/app/uploads \
  -v ./temp_images:/app/temp_images \
  ai-healthy:latest
```

## Переменные окружения

| Переменная | Значение по умолчанию | Описание |
|---|---|---|
| `DATABASE_URL` | - | PostgreSQL URL |
| `REDIS_URL` | - | Redis URL |
| `ML_SERVICE_URL` | - | ML сервис URL |
| `CELERY_BROKER_URL` | - | Celery broker |
| `CELERY_RESULT_BACKEND` | - | Celery backend |
| `ALLOWED_ORIGINS` | `[]` | CORS origins |

## Структура Dockerfile

```dockerfile
# Stage 1: Frontend build
FROM node:18-alpine AS frontend-builder
  - npm install
  - npm run build → /frontend/dist

# Stage 2: Backend + Frontend serve
FROM python:3.10-slim
  - pip install requirements.txt
  - COPY backend
  - COPY --from=frontend-builder /frontend/dist → app/static/frontend
  - CMD: uvicorn app.main:app
```

## Frontend маршрутизация

Backend сервирует frontend как SPA:
- `/` → `index.html` (SPA корневой файл)
- `/api/*` → API маршруты (обрабатываются до frontend маршрутов)
- `/*` → `index.html` (для React Router client-side routing)

## Размер образа

- Frontend build: ~200MB (уменьшается в Stage 2)
- Backend runtime: ~500-600MB (зависит от Python пакетов)
- Final image: ~600-700MB

## Оптимизация

Используется `.dockerignore` для исключения:
- `node_modules` (переустанавливаются в контейнере)
- `.git`, `__pycache__`, и т.д.
- Development файлы

## Проблемы и решения

### Frontend не загружается

1. Проверьте, что `frontend/dist` скопирован в `app/static/frontend`
2. Проверьте логи: `docker logs ai-healthy`
3. Убедитесь, что `npm run build` успешен

### Порты заняты

```bash
# Найти процесс на порту 8000
lsof -i :8000

# Или измените порт в docker-compose.yml
```

### Перестроить без кэша

```bash
docker build --no-cache -t ai-healthy:latest .
```

## Развертывание

### На сервер

```bash
# SSH на сервер
ssh user@server

# Клонировать репо
git clone https://github.com/user/ai-healthy.git
cd ai-healthy

# Запустить production
docker-compose -f docker-compose-prod.yml up -d
```

### Обновление

```bash
# Получить последние изменения
git pull

# Пересобрать
docker-compose -f docker-compose-prod.yml build

# Перезапустить
docker-compose -f docker-compose-prod.yml up -d
```

## Мониторинг

### Здоровье контейнера

```bash
docker ps --filter "name=ai-healthy"

# Детальная информация
docker inspect ai-healthy-api
```

### Логи

```bash
# Все сервисы
docker-compose logs -f

# Только API
docker-compose logs -f api

# Последние 100 строк
docker-compose logs --tail=100 api
```

## Резервная копия БД

```bash
# Из контейнера PostgreSQL
docker-compose exec db pg_dump -U ai_healthy ai_healthy > backup.sql

# Восстановление
docker-compose exec -T db psql -U ai_healthy ai_healthy < backup.sql
```

---

## Локальный запуск без Docker

Работает уже сейчас, без файлов Docker-сборки. Нужны: Python 3.10+, Node.js 18+,
локальные/удалённые PostgreSQL и Redis.

### Backend

```bash
# Виртуальное окружение (в репозитории уже есть .venv — либо создайте своё)
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# requirements.txt уже есть в корне репозитория
pip install -r requirements.txt

# .env — минимум DATABASE_URL, REDIS_URL, SECRET_KEY (32+ случайных символов),
# ADMIN_TOKEN, плюс ключи выбранного ML-провайдера (YANDEX_API_KEY/YANDEX_FOLDER_ID
# для дефолтного MODEL_PROVIDER=yandex, либо GEMINI_API_KEY и т.д.)

uvicorn app.main:app --reload --port 8000
```

### Celery worker (для асинхронного анализа фото)

```bash
celery -A app.celery_app worker --loglevel=info
```

### Telegram-бот (опционально)

```bash
set TELEGRAM_BOT_TOKEN=...   # Windows (или export на Linux/macOS)
python -m app.telegram_bot
```

### Frontend

```bash
cd frontend
npm install
npm run dev          # dev-сервер на http://localhost:5173, VITE_API_URL → http://localhost:8000
# npm run build       # прод-сборка в frontend/dist — скопируйте в app/static/frontend,
                       # чтобы FastAPI раздавал её сам (см. §7 architecture.md)
```
