# Деплой на VPS (Этап 1)

Пошаговая инструкция: поднять сервис на удалённом сервере, чтобы тестировать не одному.
Стек: FastAPI + Celery + PostgreSQL + Redis + Caddy (авто-HTTPS). Фронт собирается в Docker
и раздаётся самим FastAPI.

---

## 0. Что выбрать (настройки сервера)

| Параметр   | Рекомендация                                                |
|------------|------------------------------------------------------------|
| Провайдер  | Timeweb / Selectel / рег.ру (RU) или Hetzner (EU, дешевле)  |
| ОС         | **Ubuntu 24.04 LTS** (64-bit)                               |
| CPU/RAM    | **2 vCPU / 4 GB RAM** (без Ollama хватает)                  |
| Диск       | 40 GB SSD                                                   |
| Регион     | Ближе к тестировщикам (для RU — Москва/СПб)                 |
| Домен      | Любой дешёвый (.ru/.online) ИЛИ бесплатный DuckDNS для теста|

> Облачные модели (Yandex API) работают по сети — GPU на сервере не нужен.

---

## 1. Домен и DNS

1. Купи домен (или заведи поддомен на https://www.duckdns.org бесплатно).
2. Создай **A-запись**, указывающую на IP сервера:
   ```
   тип: A   имя: @ (или app)   значение: <IP_сервера>
   ```
3. Проверь, что резолвится (с локальной машины):
   ```bash
   nslookup myapp.ru
   ```

---

## 2. Первичная настройка сервера

Подключись по SSH (как root, данные дал провайдер):
```bash
ssh root@<IP_сервера>
```

Создай обычного пользователя и базовую защиту:
```bash
adduser deploy
usermod -aG sudo deploy

# Фаервол: оставляем только SSH + HTTP + HTTPS
ufw allow OpenSSH
ufw allow 80
ufw allow 443
ufw enable
```

Дальше работай под `deploy`:
```bash
su - deploy
```

---

## 3. Установка Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# Перелогинься, чтобы группа применилась:
exit
ssh deploy@<IP_сервера>

docker --version
docker compose version
```

---

## 4. Код на сервере

```bash
git clone <URL_твоего_репозитория> ai-healthy
cd ai-healthy
```

> Если репозиторий приватный — настрой deploy-key или клонируй по HTTPS с токеном.

---

## 5. Файл `.env` (секреты)

`.env` в git НЕ хранится — создаём его на сервере вручную.
Скопируй ключи из своего локального `.env`, но **новые/ротированные** значения для:
`SECRET_KEY`, `ADMIN_TOKEN`, `TELEGRAM_BOT_TOKEN`, API-ключи.

```bash
nano .env
```

Минимальное содержимое для прода:
```ini
# Домен (для Caddy/HTTPS)
DOMAIN=myapp.ru

# CORS: прод-домен + (позже) мобильное приложение
ALLOWED_ORIGINS_EXTRA=https://myapp.ru,capacitor://localhost

# База
DATABASE_URL=postgresql+psycopg2://fooduser:foodpass@postgres:5432/fooddb
POSTGRES_PASSWORD=adminpass

# Redis / Celery
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Модель
MODEL_PROVIDER=yandex
YANDEX_API_KEY=<новый_ключ>
YANDEX_FOLDER_ID=<твой_folder_id>
GEMINI_API_KEY=<ключ_если_нужен_fallback>

# Безопасность (СГЕНЕРИРУЙ НОВЫЕ!)
SECRET_KEY=<длинная_случайная_строка>
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
ADMIN_TOKEN=<новый_админ_токен>

# Telegram (если используешь бота)
TELEGRAM_BOT_TOKEN=<новый_токен>

# Файлы
UPLOAD_DIR=/app/app/uploads
MAX_UPLOAD_SIZE=10485760
API_URL=http://api:8000
```

Сгенерировать `SECRET_KEY`/токены:
```bash
openssl rand -hex 32
```

---

## 6. Запуск

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Первый билд (сборка фронта + установка зависимостей) — несколько минут.

Проверка:
```bash
docker compose -f docker-compose.prod.yml ps        # все сервисы healthy/running
curl -k https://myapp.ru/health                     # {"status":"ok"}
```

Открой `https://myapp.ru` в браузере → должен открыться фронт. Caddy сам выпустит
HTTPS-сертификат при первом обращении по домену (нужно, чтобы DNS уже резолвился).

---

## 7. Логи и управление

```bash
# Логи конкретного сервиса
docker compose -f docker-compose.prod.yml logs -f api
docker compose -f docker-compose.prod.yml logs -f celery_worker

# Перезапуск
docker compose -f docker-compose.prod.yml restart api

# Остановить всё
docker compose -f docker-compose.prod.yml down
```

---

## 8. Обновление (выкатка новой версии)

```bash
cd ~/ai-healthy
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

Данные (БД, загруженные фото) сохраняются на volume'ах и не теряются.

---

## 9. Бэкап БД (рекомендуется)

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres fooddb > backup_$(date +%F).sql
```

---

## Частые проблемы

- **Сертификат не выпускается** → DNS ещё не указывает на сервер, или закрыт 80/443 порт
  (нужны оба: ACME-проверка идёт по 80). Проверь `ufw status` и A-запись.
- **502 от Caddy** → API ещё стартует или упал; смотри `logs -f api`.
- **Фронт грузится, но запросы падают** → пересобери образ (`--build`): фикс относительного
  пути в axios применяется на этапе сборки фронта.
- **«Старый» фронт после обновления** → у приложения есть service worker; на телефоне/в браузере
  сделай hard-reload или очисти кэш сайта.
- **Анализ фото не работает** → проверь, что `MODEL_PROVIDER=yandex` и ключ валиден; Ollama в
  проде отсутствует, поэтому fallback на локальную модель невозможен.

---

## Тест по голому IP (без домена)

Если домена пока нет:
1. В `.env` оставь `DOMAIN` пустым.
2. В `Caddyfile` закомментируй блок `{$DOMAIN}` и раскомментируй блок `:80`.
3. `docker compose -f docker-compose.prod.yml up -d --build`
4. Открывай `http://<IP_сервера>`.

⚠️ Без HTTPS камера в мобильном браузере и установка PWA работать не будут — только для
первичной проверки API/верстки.
