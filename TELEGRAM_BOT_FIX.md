# Исправление связи Telegram Bot с API

## Проблемы, которые были найдены и исправлены:

### 1. ❌ Неправильная команда запуска telegram_bot
**Было:**
```yaml
command: python -m app.telegram_bot
```

**Стало:**
```yaml
command: python app/telegram_bot.py
```

**Причина:** Команда `python -m app.telegram_bot` не работает правильно для запуска скрипта. Нужно использовать прямой путь к файлу.

---

### 2. ❌ Отсутствие ожидания готовности API
**Проблема:** telegram_bot контейнер запускался до того, как API полностью инициализировался, даже при условии `service_started`.

**Решение:** Добавлена функция `wait_for_api()` в `app/telegram_bot.py`:
- Проверяет endpoint `/health` перед запуском бота
- До 30 попыток с 2-секундными интервалами
- Детальное логирование каждой попытки

---

### 3. ❌ Проблемы с инициализацией Redis
**Проблема:** Если Redis не был готов при загрузке модуля, бот падал с ошибкой.

**Решение:** Добавлена функция `_init_redis_client()`:
- Поддержка как `REDIS_URL`, так и `REDIS_HOST`/`REDIS_PORT`
- Проверка подключения с помощью `ping()`
- Обработка ошибок с информативным логированием

---

### 4. ⚠️ Отсутствие зависимости от Redis
**Было:**
```yaml
depends_on:
  api:
    condition: service_started
```

**Стало:**
```yaml
depends_on:
  api:
    condition: service_started
  redis:
    condition: service_healthy
```

---

## Как тестировать исправления:

### 1. Остановить текущие контейнеры
```bash
docker-compose down
```

### 2. Запустить docker-compose
```bash
docker-compose up
```

### 3. Проверить логи telegram_bot контейнера
```bash
# В отдельном терминале
docker-compose logs -f telegram_bot
```

Вы должны увидеть логи как:
```
telegram_bot_1  | INFO:__main__:Connecting to Redis at redis://redis:6379/0
telegram_bot_1  | INFO:__main__:✅ Redis connection successful
telegram_bot_1  | INFO:__main__:🔄 Waiting for API at http://api:8000...
telegram_bot_1  | INFO:__main__:✅ API is ready!
telegram_bot_1  | INFO:__main__:Starting Telegram bot
```

### 4. Проверить логи API контейнера
```bash
docker-compose logs -f api
```

---

## Что нужно отправить боту для проверки:

1. **Отправить `/start`** - должен показать главное меню
2. **Отправить фото** - бот должен его загрузить и отправить на анализ
3. **Посмотреть результат** - должна прийти информация о блюде и калориях

---

## Если всё ещё не работает:

### Проверить сетевое соединение
```bash
# Проверить, видит ли telegram_bot контейнер API
docker-compose exec telegram_bot curl -v http://api:8000/health
```

### Проверить Redis
```bash
docker-compose exec telegram_bot redis-cli -h redis ping
```

### Проверить переменные окружения
```bash
docker-compose exec telegram_bot env | grep -E 'API_URL|REDIS|TOKEN'
```

---

## Изменённые файлы:

- ✅ [app/telegram_bot.py](app/telegram_bot.py) - добавлена инициализация и ожидание API
- ✅ [docker-compose.yml](docker-compose.yml) - исправлена команда запуска и зависимости

---

**Если ошибки всё ещё возникают, проверьте консоль docker-compose и поделитесь логами для более детального анализа.**
