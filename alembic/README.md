# Миграции БД (Alembic)

Схема версионируется через Alembic. Историческая часть (все таблицы до этого
момента) создавалась `Base.metadata.create_all()` на старте приложения и
самописным `ensure_schema()` в `app/database.py`; они пока остаются, чтобы
существующая БД и тесты не сломались. Все НОВЫЕ изменения схемы оформляем
миграциями Alembic.

## Применить миграции (прод)

```bash
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
```

На уже существующей БД первая ревизия `0001` просто дропнет пустые legacy-таблицы
(`meals`, `meal_items`, `photos`). Данных там нет, откат безопасен.

## Создать новую миграцию

```bash
docker compose -f docker-compose.prod.yml exec api \
  alembic revision --autogenerate -m "краткое описание"
```

`--autogenerate` сравнивает `app.models` (Base.metadata) с реальной БД. Всегда
просматривай сгенерированный файл перед `upgrade`.

## Куда двигаться дальше

Когда все окружения будут проходить через Alembic, из `app/main.py` можно убрать
`ensure_schema()` в пользу `alembic upgrade head` на старте — тогда Alembic станет
единственным источником правды по схеме.
