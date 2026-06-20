# Запуск проекта на своём ПК (dev / test + туннель)

Два независимых окружения. Изолированы по имени проекта (свои тома/БД), портам и кредам — могут работать одновременно.

| | **DEV** (для разработки) | **TEST** (для друзей/жены) |
|---|---|---|
| Compose-файл | `docker-compose.dev.yml` | `docker-compose.test.yml` |
| Креды | `.env.dev` | `.env.test` |
| Проект / тома | `ai-healthy-dev_*` | `ai-healthy-test_*` |
| Доступ | только локально (127.0.0.1) | наружу через туннель |
| Фронт | vite c hot-reload, порт **5173** | вшит в образ, раздаётся API |
| API | **8000** | **8001** |
| Postgres | **5433** | **5434** |
| Код | смонтирован, авто-reload | вшит в образ (выкатка через `--build`) |

> Все команды — в PowerShell из папки проекта. Docker Desktop должен быть запущен.

---

## DEV — разработка (только для себя)

```powershell
docker compose -f docker-compose.dev.yml up -d --build     # старт
```
Открывай **http://localhost:5173** (vite, ходит в API на :8000). Правки `.py` и `.tsx` применяются на лету.

```powershell
docker compose -f docker-compose.dev.yml logs -f api       # логи
docker compose -f docker-compose.dev.yml down              # стоп
```

---

## TEST — для друзей/жены (шарится наружу)

### 1. Поднять стек
```powershell
docker compose -f docker-compose.test.yml up -d --build
```
Проверка локально: **http://localhost:8001**

### 2. Поднять туннель (внешний HTTPS-доступ)
В этой сети **cloudflared не работает** (закрыт порт 7844) — используем **ngrok** (ходит по 443).

Первый запуск (создаёт контейнер):
```powershell
docker run -d --name ai-tunnel -p 4040:4040 -e NGROK_AUTHTOKEN=<твой_токен> `
  ngrok/ngrok:latest http host.docker.internal:8001
```
Токен — на https://dashboard.ngrok.com/get-started/your-authtoken

### 3. Узнать публичную ссылку
```powershell
docker logs ai-tunnel | Select-String "url="
```
Или открой панель **http://localhost:4040** (там же видны все запросы — удобно дебажить).

Ссылку вида `https://<random>.ngrok-free.dev` отдаёшь тестировщикам.
> На первом экране ngrok нужно один раз нажать **Visit Site**.

### Выкатить новый код в test
```powershell
docker compose -f docker-compose.test.yml up -d --build
```

---

## Остановить / запустить заново

### Полная остановка
```powershell
docker stop ai-tunnel                                  # 1. туннель (это ОТДЕЛЬНЫЙ контейнер!)
docker compose -f docker-compose.test.yml down         # 2. test-стек
docker compose -f docker-compose.dev.yml down          # 3. dev-стек (если запускал)
```
> `ai-tunnel` не входит в compose-стек — `down`/`stop` на стеке его не останавливает. Останавливать отдельно.

### Запустить заново
```powershell
docker compose -f docker-compose.test.yml up -d        # стек (--build только если менял код)
docker start ai-tunnel                                  # туннель
docker logs ai-tunnel | Select-String "url="           # узнать НОВЫЙ адрес
```
⚠️ На бесплатном ngrok ссылка **меняется при каждом перезапуске** туннеля — раздавай новый адрес. (Постоянный адрес — через static domain в аккаунте ngrok.)

### Что значат команды
- `stop` — пауза, контейнеры и данные остаются, старт мгновенный.
- `down` — удаляет контейнеры, **данные БД/фото сохраняются** (named volumes).
- `down -v` — удаляет И данные (полностью чистый старт). Использовать осознанно.

---

## Подключение к базам (DBeaver / psql)

| | Host | Port | DB | User / Password |
|---|---|---|---|---|
| DEV | localhost | 5433 | fooddb | `postgres` / `adminpass` или `fooduser` / `foodpass` |
| TEST | localhost | 5434 | fooddb | `postgres` / `testpass` или `fooduser` / `foodpass` |

Быстро в консоли:
```powershell
docker compose -f docker-compose.test.yml exec postgres psql -U postgres -d fooddb
```

---

## Частые проблемы

- **«Старый» фронт у тестировщиков** → у приложения есть service worker (кэш). Закрыть вкладку и открыть заново, либо очистить данные сайта / hard-reload.
- **`pull access denied for ai-healthy`** → у сервиса нет `build:`. Все сервисы, использующие образ `ai-healthy:*`, должны иметь `build: .` (уже исправлено в compose-файлах).
- **Туннель не поднимается, `port 7844`** → это про cloudflared, он тут не работает. Использовать ngrok (см. выше).
- **Страницы /profile, /meals и т.п. дают 404 при прямом заходе** → нужен SPA-fallback на бэкенде (уже добавлен: `SPAStaticFiles` в `app/main.py`). После правок фронта пересобрать test.
- **Анализ фото не работает** → проверь `MODEL_PROVIDER=yandex` и валидность ключа в `.env.test`; Ollama в этих стеках нет.

---

## Файлы окружения

`.env.dev` и `.env.test` созданы из `.env` с **разными** `SECRET_KEY`/`ADMIN_TOKEN` (в git не коммитятся). API-ключи (Yandex/Gemini) общие — нужны для распознавания еды. Для внешнего test-стека ключи стоит периодически ротировать.
