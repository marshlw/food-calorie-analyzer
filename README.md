# AI Healthy 🥗

Сервис распознавания еды и анализа питательной ценности по фотографии. Пользователь загружает фото блюда — система определяет блюдо и рассчитывает КБЖУ (калории, белки, жиры, углеводы), ведёт дневник питания и собирает обратную связь для дообучения.

## Возможности

- 📸 Анализ блюда по фото несколькими ML-провайдерами (Yandex / Gemini / Ollama / DeepSeek)
- 📓 Дневник питания: дневная статистика и приёмы пищи
- 🔐 Аутентификация по JWT (access/refresh-токены)
- 🤖 Telegram-бот
- 🔁 Обратная связь пользователей для улучшения распознавания

## Технологический стек

- **Backend:** FastAPI, SQLAlchemy, Pydantic
- **Очереди/кэш:** Celery + Redis
- **БД:** PostgreSQL
- **ML:** Yandex Vision / Gemini / Ollama (llava) / DeepSeek
- **Frontend:** React + TypeScript + Vite + Tailwind
- **Инфраструктура:** Docker / docker-compose (сервисы: `api`, `celery_worker`, `telegram_bot`, `postgres`, `redis`, `ollama`, `gradio`)

## Быстрый старт

```bash
# 1. Скопируйте и заполните переменные окружения
cp .env.example .env   # при наличии; см. app/config.py для списка переменных

# 2. Запустите весь стек через Docker
docker-compose up -d
# либо интерактивно:
./docker-start.sh

# API будет доступно на http://localhost:8000
# Swagger UI: http://localhost:8000/docs
```

Запуск фронтенда для разработки — см. [docs/frontend/README.md](docs/frontend/README.md).

## Структура проекта

```
app/         — backend (FastAPI, ML-сервис, Celery-задачи, Telegram-бот)
frontend/    — React/TypeScript веб-приложение
docs/        — вся документация проекта (см. ниже)
docker-compose.yml, Dockerfile — инфраструктура
```

## 📚 Документация

Вся документация собрана в папке [`docs/`](docs/README.md). Кратко:

| Раздел | Документ |
|--------|----------|
| Архитектура | [Обзор](docs/architecture/architecture.md) · [Auth flow](docs/architecture/auth_flow.md) · [Жизненный цикл задачи](docs/architecture/task_lifecycle.md) · [Аудит кода](docs/architecture/code_audit.md) |
| Установка | [Docker](docs/setup/DOCKER.md) |
| API | [Postman-коллекция](docs/api/POSTMAN_README.md) |
| Фронтенд | [README](docs/frontend/README.md) · [Setup Complete](docs/frontend/SETUP_COMPLETE.md) |
| Отладка | [API ↔ Frontend](docs/troubleshooting/API_DEBUG.md) · [Сводка исправлений](docs/troubleshooting/FIXES_SUMMARY.md) · [Telegram Bot](docs/troubleshooting/TELEGRAM_BOT_FIX.md) |

Полный индекс: [docs/README.md](docs/README.md).
