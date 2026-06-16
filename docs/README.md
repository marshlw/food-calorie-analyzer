# Документация AI Healthy

Единая точка входа для всей документации проекта. Файлы сгруппированы по назначению.

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
