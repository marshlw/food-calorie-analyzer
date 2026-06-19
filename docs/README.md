# Документация AI Healthy

Единая точка входа для всей документации проекта. Файлы сгруппированы по назначению.

**AI Healthy** — приложение для учёта питания с автоматическим распознаванием КБЖУ
(калории/белки/жиры/углеводы) по фотографии блюда. Бэкенд — FastAPI + PostgreSQL + Redis +
Celery, фронтенд — React (Vite, PWA).

---

## 📋 Документация для QA (автотесты)

Полный комплект для написания автотестов: требования, спецификация API и готовые коллекции.

### Требования

- [Функциональные требования](requirements/functional-requirements.md) — что система должна делать (по модулям, с ID требований).
- [Нефункциональные требования](requirements/non-functional-requirements.md) — безопасность, производительность, надёжность.
- [Модели данных](requirements/data-models.md) — сущности БД и схемы обмена (контракты), ограничения полей.
- [Бизнес-правила](requirements/business-rules.md) — формулы BMR/КБЖУ, жизненный цикл задач, валидации, пограничные случаи.

### API

- [Сводка эндпоинтов](api/api-endpoints-summary.md) — краткое описание всех ручек, коды ошибок, советы для тестов.
- [OpenAPI 3.0 спецификация](api/swagger.yaml) — машинно-читаемый контракт (Swagger).
- [Postman-коллекция](api/postman-collection.json) — готовая коллекция (v2.1), соответствующая спецификации.

> **Быстрый старт для QA:** импортируйте `api/postman-collection.json` в Postman, задайте
> переменные `base_url`, `email`, `password`, выполните `Register` → `Login` (токены
> сохранятся автоматически), затем запускайте остальные запросы. Базовый URL по умолчанию —
> `http://localhost:8000`. Интерактивный Swagger UI доступен по `/docs`.

---

## 🏗 Архитектура

- [Обзор архитектуры](architecture/architecture.md) — компоненты системы, потоки данных, ML-сервис.
- [Аутентификация](architecture/auth_flow.md) — JWT access/refresh-токены, флоу авторизации.
- [Жизненный цикл задачи](architecture/task_lifecycle.md) — статусы анализа изображения.
- [Аудит кода](architecture/code_audit.md) — состояние тестов и качество кода.

## ⚙️ Установка и запуск

- [Docker](setup/DOCKER.md) — сборка и запуск через Docker / docker-compose.

## 🔌 API

- [Postman-коллекция](api/POSTMAN_README.md) — импорт и использование коллекции запросов к API.

## 🎨 Фронтенд

- [Frontend README](frontend/README.md) — стек, структура и запуск React-приложения.
- [Setup Complete](frontend/SETUP_COMPLETE.md) — что входит в готовую сборку фронтенда.

## 🛠 Отладка и история исправлений

- [Интеграция API ↔ Frontend](troubleshooting/API_DEBUG.md) — типовые проблемы и решения.
- [Сводка исправлений](troubleshooting/FIXES_SUMMARY.md) — что и почему было исправлено.
- [Исправление Telegram-бота](troubleshooting/TELEGRAM_BOT_FIX.md) — связь бота с API.
