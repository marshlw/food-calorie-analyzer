# Безопасность БД и раскатка изменений

Короткая памятка по двум изменениям: (1) усиление паролей прод-БД и
(2) переход схемы на миграции Alembic + удаление мёртвых таблиц.

## Что поменялось

**Пароли БД.**
- Из `docker-compose.prod.yml` убран слабый дефолт `adminpass`. Теперь
  `POSTGRES_PASSWORD` и `APP_DB_PASSWORD` **обязательны** — без них compose
  не стартует (`:?`).
- Пароль `fooduser` больше не хардкодится: `init.sql` → `init.sh`, пароль
  берётся из `APP_DB_PASSWORD`.
- В `app/config.py` добавлен fail-fast: приложение **не поднимется**, если в
  `DATABASE_URL` слабый/словарный пароль (`foodpass`, `adminpass`, ...), пока
  явно не выставлен `ALLOW_INSECURE_DB_PASSWORD=true` (только для dev/test).

**Схема.**
- Заведён Alembic (`alembic.ini`, `alembic/`). Первая ревизия `0001` дропает
  пустые legacy-таблицы `meals`, `meal_items`, `photos`.
- Модели `Meal`/`MealItem`/`Photo` и их Pydantic-схемы удалены из кода.

## Раскатка на новом деплое (чистый том)

1. Сгенерируй секреты:
   ```bash
   python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32))"
   python3 -c "import secrets; print('APP_DB_PASSWORD='  + secrets.token_urlsafe(32))"
   python3 -c "import secrets; print('SECRET_KEY='       + secrets.token_urlsafe(48))"
   ```
2. Впиши их в `.env` (см. `.env.example`). В `DATABASE_URL` пароль = `APP_DB_PASSWORD`.
3. Старт:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   docker compose -f docker-compose.prod.yml exec api alembic upgrade head
   ```

## Ротация пароля на УЖЕ работающей проде

`init.sh` выполняется только на пустом томе, поэтому пароль существующего
`fooduser` меняется вручную:

1. Сгенерируй новый `APP_DB_PASSWORD` (команда выше).
2. Смени пароль роли в живой БД:
   ```bash
   docker compose -f docker-compose.prod.yml exec postgres \
     psql -U postgres -d fooddb -c "ALTER ROLE fooduser WITH PASSWORD 'НОВЫЙ_ПАРОЛЬ';"
   ```
3. Смени пароль суперпользователя `postgres` (был `adminpass`):
   ```bash
   docker compose -f docker-compose.prod.yml exec postgres \
     psql -U postgres -c "ALTER ROLE postgres WITH PASSWORD 'НОВЫЙ_СУПЕР_ПАРОЛЬ';"
   ```
4. Обнови `.env`: `POSTGRES_PASSWORD`, `APP_DB_PASSWORD` и пароль внутри
   `DATABASE_URL`.
5. Перезапусти сервисы, использующие БД:
   ```bash
   docker compose -f docker-compose.prod.yml up -d
   ```

## Применить дроп legacy-таблиц на существующей БД

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```
Таблицы пустые, откат безопасен (`alembic downgrade -1` их воссоздаст пустыми).

## Проверка

```bash
# таблиц meals/meal_items/photos больше нет:
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U postgres -d fooddb -c "\dt" | grep -E 'meals|meal_items|photos' || echo "OK: удалены"

# приложение видит новый пароль (нет ошибок аутентификации):
docker compose -f docker-compose.prod.yml logs --tail=50 api
```

## Важно про секреты

Файлы `.env*` в `.gitignore` — в репозиторий не попадают. Но если текущий `.env`
когда-либо коммитился или лежал в общем доступе, разово **проверь историю git** и
при необходимости **ротируй все ключи** (DB, `SECRET_KEY`, API-ключи Yandex/Gemini/
DeepSeek, `TELEGRAM_BOT_TOKEN`, `ADMIN_TOKEN`), т.к. они были в рабочем каталоге.
