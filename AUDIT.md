# Аудит проекта ai-healthy

Дата: 28.07.2026
Область: `app/*.py` (FastAPI + Celery + SQLAlchemy), `frontend/src`, `docker-compose.prod.yml`, `Dockerfile`, `Caddyfile`, `init.sh`.

> **Статус исправлений (спринт 1, 28.07.2026)**
>
> | # | Статус | Что сделано |
> |---|---|---|
> | C-1 | ✅ исправлено | `POST /meals` проверяет владение `task_id`; `HTTPException` больше не превращается в 500 |
> | C-2 | ✅ исправлено | дубль `get_db` в `main.py` удалён (одна сессия на запрос), пул снижен до 5+5, `pool_timeout=10`, `max_connections=150` |
> | C-3 | ✅ исправлено | все эндпоинты с БД/диском переведены в `def`; `async def` остался у `/health`, `/me` и советчика; лимит threadpool зафиксирован |
> | H-1 | ✅ исправлено | CSP в `Caddyfile`; inline-скрипт темы вынесен в `/theme.js` |
> | H-3 | ✅ исправлено | `--forwarded-allow-ips` = статический IP caddy; Caddy перезаписывает XFF |
> | C-4, C-5, H-2, H-4…H-7, M-*, раздел 4 | ⏳ не начато | см. спринты 2 и 3 |

Общая оценка: базовая гигиена безопасности заметно выше среднего — есть HMAC-подписи фото, token_version для инвалидации JWT, brute-force защита, валидация загрузок, guard на weak secrets. Проблемы сосредоточены в трёх местах: **одна дыра IDOR**, **архитектурный дефект `async def` + синхронный SQLAlchemy** и **вместимость под 5000 DAU** (пул соединений, пропускная способность Celery, диск).

---

## 1. Критично (чинить до продакшена)

### C-1. IDOR: чужое фото еды через `task_id` в `POST /api/v1/meals`

`main.py:697-709`

```python
return crud.add_meal_entry(db, current_user.id, meal, target_date=meal.date, task_id=meal.task_id)
```

`meal.task_id` приходит **из тела запроса и никак не проверяется на принадлежность пользователю**. В `models.MealEntry.photo_url` (`models.py:169-178`):

```python
if self.task_id and self.task and self.task.image_path:
    return signed_upload_url(self.task.image_path)
```

Итог: злоумышленник перебирает/угадывает `task_id` (UUID, но их можно получить из своих же ответов при утечке, а также через `POST /api/v1/meals` с чужим id), создаёт себе приём пищи и получает **валидную подписанную ссылку на фото другого пользователя**. Сравните с `add_meal_from_analysis` (`main.py:843-845`), где проверка есть — здесь её просто забыли.

Побочно: несуществующий `task_id` роняет FK-констрейнт → 500.

**Фикс:**

```python
task_id = None
if meal.task_id:
    task = crud.get_task_by_id_sync(db, meal.task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    task_id = task.id
return crud.add_meal_entry(db, current_user.id, meal, target_date=meal.date, task_id=task_id)
```

---

### C-2. Пул соединений к БД гарантированно исчерпает Postgres

`config.py:17-18`, `docker-compose.prod.yml:85,109`

- api: `--workers 2` × (`DB_POOL_SIZE=10` + `DB_MAX_OVERFLOW=20`) = **60**
- celery: `--concurrency=4` × 30 = **120**

Итого до **180** коннектов при `max_connections` Postgres по умолчанию = **100**. Под пиком получите `FATAL: sorry, too many clients already` — причём отвалится и API, и воркеры.

Усугубляется тем, что **на один HTTP-запрос берётся ДВА соединения**: `auth.get_current_user` использует `database.get_db`, а эндпоинты — свою `main.get_db` (`main.py:198-203`). Это прямо задокументировано в `crud.py:264-268` как известное расхождение. Реальная потребность в коннектах вдвое выше расчётной.

**Фикс (по возрастанию радикальности):**
1. Убрать дубликат `get_db` в `main.py`, импортировать `from .database import get_db` — минус 50% коннектов, минус лишний `SELECT users` на каждый запрос.
2. Снизить до `DB_POOL_SIZE=5`, `DB_MAX_OVERFLOW=5` и поднять `max_connections=200` в Postgres.
3. Правильное решение под 5000 DAU — **PgBouncer** в режиме `transaction` между приложением и Postgres.

---

### C-3. `async def` + синхронный SQLAlchemy = блокировка event loop

Это главный тормоз под нагрузкой. Практически все эндпоинты объявлены `async def`, но внутри делают **синхронные** запросы psycopg2:

`get_profile`, `update_profile`, `add_weight_record`, `update_weight_record`, `get_weight_history`, `search_products`, `search_exercises`, `get_task`, `get_user_tasks`, `add_meal`, `edit_meal_entry`, `delete_meal_entry`, `get_daily_log`, `get_water`, `update_water`, `add_meal_from_analysis`, `submit_feedback`, `get_workouts`, `add_workout`, `update_workout`, `delete_workout`, все `admin/*`.

В `async def` синхронный вызов выполняется **прямо в event loop**. Пока идёт запрос к БД (даже 5 мс), воркер не обрабатывает ничего другого. При 2 воркерах эффективная пропускная способность API = 2 × (1 / средняя_длительность_запроса). Диагноз подтверждается тем, что авторы это знали для auth-эндпоинтов (`main.py:294-296` — там честно `def`), но не применили правило ко всему остальному.

Отдельно тяжёлые случаи:
- `analyze` (`main.py:254`) — `async def`, внутри `_save_upload_file_securely`: чтение до 10 МБ файла чанками по 8 КБ + `PIL.verify()` **в event loop**. Одна загрузка фото на медленном мобильном канале подвешивает весь воркер.
- `upload_meal_photo` (`main.py:931`) — то же самое.

**Фикс:** механически заменить `async def` → `def` у всех эндпоинтов, которые ходят в БД или на диск. FastAPI сам уведёт их в threadpool. Исключение — `get_advisor` / `ask_advisor`, они уже сделаны правильно (`run_in_threadpool` + отдельный `_llm_executor`). После этого поднять `anyio` threadpool: `anyio.to_thread.current_default_thread_limiter().total_tokens = 80` (дефолт 40).

---

### C-4. Пропускная способность Celery не покрывает заявленную нагрузку

`docker-compose.prod.yml:109` — `--concurrency=4`, один анализ фото через Yandex Vision занимает 20–45 с (`MODEL_TIMEOUT_SECONDS=45`, `soft_time_limit=540`).

Потолок: 4 / 30 с ≈ **0,13 задачи/с ≈ 11 500 в сутки** — и это при идеальной равномерности.

Реальность: 5000 DAU × `AI_DAILY_LIMIT=5` = до 25 000 запросов/сутки, при этом трафик пиковый (завтрак/обед/ужин). В пик 19:00–21:00 может прийти 30–40% дневного объёма → очередь Redis растёт, пользователь ждёт результат десятки минут, а фронт опрашивает `/api/v1/task/{id}` всё это время.

**Фикс:**
- Отдельный пул воркеров под анализ (`-Q analyze`) с `--concurrency=8..16` (задача I/O-bound — ждёт HTTP, не CPU) и отдельная очередь под `retrain`.
- Ограничить общую конкуррентность внешнего API семафором, чтобы не словить 429 от Yandex.
- Снизить `AI_DAILY_LIMIT` до 3 либо ввести глобальный лимит на минуту.
- Показывать в UI позицию в очереди.
- Кэш по SHA-256 фото (`ml_service.py:1146`) уже есть — это хорошо, но помогает только на повторах.

---

### C-5. Диск переполнится

`config.py:104` — `DELETE_UPLOAD_AFTER_ANALYSIS: bool = False`, никакого job'а очистки в проекте нет. Том `uploads_data` растёт монотонно.

Оценка: 5000 DAU × 1,5 фото × ~400 КБ ≈ **3 ГБ/сутки ≈ 90 ГБ/месяц**. На арендованной ВМ (судя по комментарию в compose — 2 ГБ RAM, значит и диск небольшой) это недели две до `No space left on device`, после чего упадёт и Postgres.

В репозитории уже лежит ~12 000 накопленных jpg в `app/app/uploads` и `app/uploads` — симптом того, что чистки нет вообще.

**Фикс:**
- Периодическая celery-beat задача: удалять файлы из `UPLOAD_DIR` старше N дней, у которых нет ссылок из `tasks.image_path` / `meal_entries.photo_path`.
- Или вынести хранение в S3/Object Storage с lifecycle-политикой.
- Плюс мониторинг свободного места.

---

## 2. Высокий приоритет

### H-1. Нет CSP, а JWT лежит в localStorage

`frontend/src/api/axios.ts:22,76-77,119-120` — access и refresh токены в `localStorage`. В `Caddyfile` есть HSTS, nosniff, X-Frame-Options, но **нет `Content-Security-Policy`**, хотя комментарий в `main.py:59` обещает, что CSP добавляется на reverse-proxy.

Любой XSS (в т.ч. через скомпрометированную npm-зависимость фронта) = кража refresh-токена на 7 дней.

**Фикс:** добавить в `Caddyfile`:
```
Content-Security-Policy "default-src 'self'; img-src 'self' data: https://images.openfoodfacts.org; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
```
Долгосрочно — refresh-токен в `HttpOnly; Secure; SameSite=Strict` cookie, access — в памяти JS.

### H-2. Refresh-токены не ротируются и не отзываются

`main.py:367-381` — при `grant_type=refresh_token` выдаётся новая пара, но **старый refresh продолжает работать** до `exp` (7 дней). Нет `jti`, нет denylist, нет детекции повторного использования.

Украденный refresh даёт злоумышленнику 7 дней доступа параллельно с легитимным пользователем, и это никак не обнаруживается. `token_version` спасает только при явной смене пароля.

**Фикс:** ротация с одноразовым использованием — хранить `jti` активного refresh в Redis (`refresh:{user_id}:{jti}`), при использовании удалять и выдавать новый; повторное предъявление уже погашенного `jti` → инвалидировать всю сессию (bump `token_version`).

### H-3. `--forwarded-allow-ips '*'` ослабляет brute-force защиту

`docker-compose.prod.yml:85`

`rate_limit.get_client_ip` (`rate_limit.py:135-145`) написан аккуратно — он доверяет `X-Forwarded-For` только от приватного peer'а. Но uvicorn с `--forwarded-allow-ips '*'` **уже переписал `request.client.host`** значением из заголовка до того, как код до него добрался. Вся защита (лимиты по IP на login/register, счётчик неудачных входов) обходится подстановкой случайного `X-Forwarded-For` в каждый запрос.

**Фикс:** заменить `'*'` на подсеть сети `web` (например `--forwarded-allow-ips '172.16.0.0/12'`) либо на IP контейнера caddy. И убедиться, что Caddy **перезаписывает**, а не дополняет XFF.

### H-4. `GET /api/v1/advisor` без rate-limit

`main.py:1109-1115`. У `/advisor/ask` лимит есть (30/сутки), у `/advisor` — нет. Ключ кэша (`advisor.py:352-357`) содержит хэш всего контекста дня, включая съеденные калории. Значит **любое изменение дневника инвалидирует кэш** и следующее открытие вкладки = новый LLM-вызов на 40 секунд.

Один активный пользователь легко делает 20–30 LLM-вызовов в день. При 5000 DAU это счёт за токены и постоянно забитый `_llm_executor` (8 слотов) — очередь в `run_in_executor` растёт без ограничения и без таймаута.

**Фикс:** такой же `rate_limit.enforce` как у `/ask` (например 20/сутки); огрубить fingerprint контекста (округлять калории до 100, воду до 250 мл); добавить `asyncio.wait_for` на `run_in_executor`.

### H-5. Decompression bomb в Celery-воркере

`ml_service.py:928` — `Image.MAX_IMAGE_PIXELS = 100000000` (100 Мп, выше дефолта PIL 89 Мп). `_validate_uploaded_image` (`main.py:146-154`) вызывает только `img.verify()`, который **не декодирует пиксели**. Фактическое декодирование происходит в `preprocess` уже в воркере.

10-мегабайтный PNG может развернуться в 100 Мп × 3 байта ≈ **300 МБ RSS** на изображение. При `--concurrency=4` это 1,2 ГБ на ВМ с 2 ГБ RAM → OOM-killer сносит воркер, задачи с `acks_late=True` возвращаются в очередь и цикл повторяется.

**Фикс:** проверять `img.size` сразу после загрузки в `_save_upload_file_securely` и отклонять всё, что больше ~30 Мп; снизить `MAX_IMAGE_PIXELS` до 30_000_000; выставить memory limit контейнеру celery.

### H-6. Ретрейн модели сломан и зациклен

`tasks.py:105`:
```python
script_path = Path(__file__).parent.parent / "training_data" / "generate_dataset.py"
```
`__file__` = `/app/app/tasks.py` → путь получается `/app/training_data/generate_dataset.py`, а файл лежит в `/app/app/training_data/generate_dataset.py`. **Путь неверный.**

Дальше `subprocess.run(["ollama", ...])` — бинарника `ollama` в прод-образе нет (compose это прямо декларирует: «нет ollama, MODEL_PROVIDER=yandex»).

Guard `retrain:queued` снимается в `finally` (`tasks.py:134-139`), а `pending_count` при этом не уменьшается — значит **каждый следующий фидбек после 10-го снова ставит заведомо падающую задачу**. Плюс `subprocess.run` без `timeout`.

**Фикс:** либо убрать триггер ретрейна из `create_feedback_sync`, либо чинить путь + вынести ретрейн в отдельную очередь и не снимать guard при неудаче (оставлять TTL как backoff).

### H-7. Схема БД управляется ad-hoc DDL при каждом старте

`database.py:118-151` + `main.py:82-126`. Alembic в проекте есть (`alembic.ini`), но не используется. Вместо этого при старте **каждого** воркера выполняются:
- `create_all()`,
- `CREATE INDEX IF NOT EXISTS` — **без `CONCURRENTLY`**, то есть с блокировкой таблицы на запись,
- цепочка `ALTER TABLE ... ADD COLUMN`,
- `seed_products` / `seed_exercises`,
- `backfill_meal_protein_split` — **полное сканирование `meal_entries` и `meal_entry_items` с загрузкой всех подходящих строк в память Python**.

Два воркера стартуют одновременно → гонка на DDL. С ростом таблицы приёмов (при 5000 DAU это ~20 000 строк/сутки) backfill на старте превратится в многосекундную блокировку деплоя, а `ADD COLUMN` на живой таблице возьмёт `ACCESS EXCLUSIVE` lock.

**Фикс:** перенести всё в Alembic-миграции, запускать одной командой в CI/деплое, из startup-хука убрать. Оставить в startup максимум прогрев HTTP/Redis клиентов.

---

## 3. Средний приоритет

| # | Находка | Где | Комментарий |
|---|---|---|---|
| M-1 | `ilike '%слово%'` в автодополнении | `crud.py:775, 839` | Ведущий wildcard **не может использовать B-tree индекс** → seq scan `products` (~700 строк, растёт) и `exercises` на каждое нажатие клавиши. Самый частый запрос в приложении. Фикс: `CREATE EXTENSION pg_trgm; CREATE INDEX ... USING gin (lower(name) gin_trgm_ops);` |
| M-2 | `literal(norm).like('%'\|\|Product.name\|\|'%')` | `ml_service.py:1002` | Индекс невозможен в принципе — full scan `products` на **каждый ингредиент каждого анализа** (до 6 раз). В воркере, но всё равно лишние сотни мс. Фикс: загрузить справочник в память процесса один раз (он мал и почти не меняется). |
| M-3 | Redis без пароля | `docker-compose.prod.yml:65-78` | Хранит JWT telegram-бота, пароли TG-аккаунтов в открытом виде (`telegram_bot.py:100-109`), очередь Celery, все rate-limit счётчики. Защищён только сетевой изоляцией — при любой ошибке в конфигурации сети всё уезжает. Фикс: `--requirepass` + `REDIS_URL` с паролем. |
| M-4 | Postgres опубликован наружу вопреки комментарию | `docker-compose.prod.yml:55-56` | Шапка файла утверждает «ни одного `ports:`», но порт `127.0.0.1:5433:5432` есть. Не критично (только loopback), но комментарий врёт — при следующей правке легко превратится в `0.0.0.0`. |
| M-5 | 12 000 картинок и `.venv` попадают в docker-образ | `.dockerignore`, `Dockerfile:29` | `COPY . .` тянет `app/app/uploads/*` и `app/training_data/images/*`. Образ раздут на сотни МБ, деплой медленный. Фикс: добавить в `.dockerignore` строки `app/app/uploads/`, `app/uploads/`, `app/temp_images/`, `**/training_data/images/`, `.venv/`, `.pytest_cache/`. |
| M-6 | Контейнер работает от root | `Dockerfile` | Нет `USER`. `no-new-privileges` есть, но это не то же самое. Фикс: `RUN useradd -m app && chown -R app /app` + `USER app`. |
| M-7 | `datetime.utcnow()` в tz-aware колонки | `crud.py:370`, `tasks.py:48` | Колонки объявлены `DateTime(timezone=True)` с `server_default=func.now()` (aware), а код пишет naive. В Postgres это интерпретируется как локальное время сессии → расхождение и некорректная сортировка `created_at`/`updated_at`. Фикс: `datetime.now(timezone.utc)`. |
| M-8 | `analyze_image_sync` глотает все ошибки | `ml_service.py:1214-1221` | Возвращает `DEFAULT_FALLBACK` (`food: "unknown"`, 200 ккал) вместо исключения. Из-за этого `autoretry_for=(Exception,)` в задаче **никогда не срабатывает**, задача помечается SUCCESS, лимит пользователя списан, результат — мусор. Фикс: пробрасывать исключение при полном отказе всех провайдеров, чтобы отработал retry и `refund`. |
| M-9 | CORS с localhost и `allow_credentials=True` в проде | `config.py:116-126`, `main.py:36-43` | Восемь localhost-origin'ов зашиты в дефолт и не убираются в проде. `expose_headers=["*"]` вместе с credentials — невалидная по спецификации комбинация. Фикс: пустой дефолт + только `ALLOWED_ORIGINS_EXTRA` в проде. |
| M-10 | `POST /api/v1/meals` не проверяет дату | `main.py:697` | Для воды, тренировок и веса проверка «не в будущем» есть, для приёмов пищи — нет. Можно записать еду на 2099 год. |
| M-11 | Нет индекса на `feedback.status` | `models.py:357` | `create_feedback_sync` делает `COUNT(*) WHERE status='pending'` на **каждом** фидбеке. |
| M-12 | In-memory fallback rate-limit | `rate_limit.py:24-61` | При падении Redis лимиты становятся **пер-процессные** → при 2 воркерах реальный лимит удваивается, при рестарте обнуляется. Приемлемо как деградация, но должно логироваться как алерт, а не `warning` раз в запрос. |
| M-13 | Админ-эндпоинты без rate-limit | `main.py:1144-1150` | `compare_digest` защищает от timing-атак, но не от онлайн-перебора. Плюс: если `x_admin_token` содержит не-ASCII, `compare_digest` бросит `TypeError` → 500. Фикс: `enforce()` по IP + обернуть в try/except. |
| M-14 | `exception_handler(Exception)` с `raise exc` | `main.py:66-74` | Ре-raise внутри `ServerErrorMiddleware` приводит к обрыву соединения без тела ответа. На практике не срабатывает (HTTPException перехватывается раньше), но код мёртвый и вводит в заблуждение. |

---

## 4. Низкий приоритет / гигиена

- `utils.py` — дублирующиеся импорты (`PIL.Image`, `hashlib`, `magic` дважды), `except:` без типа в `validate_image_file` (строка 149), мёртвые функции `validate_image_file` / `process_image` / `generate_thumbnail` / `compute_file_hash` — нигде не вызываются.
- `crud.learn_products_from_feedback` — мёртвый код с честным предупреждением в докстринге. Лучше удалить, чем оставлять мину.
- Нет ограничения длины пароля сверху и нет требований к сложности (только `min_length=8`).
- Нет верификации email при регистрации — регистрироваться можно на чужой адрес.
- `_build_profile` вызывает `get_latest_weight` дважды (напрямую и внутри `compute_nutrition_targets`); `_build_workouts_payload` дважды вызывает `list_workouts`. Мелочь, но на горячем пути.
- `pydantic` v1-стиль (`@validator`, `@root_validator`) на pydantic 2.6 — работает через слой совместимости, при обновлении сломается.
- Нет структурированного логирования/трейсинга и метрик — под 5000 DAU диагностировать инциденты будет нечем. Минимум: `prometheus-fastapi-instrumentator` + Sentry.
- `pip install` без `--no-cache-dir` для `gcc` — `gcc` остаётся в финальном образе (не multi-stage для Python части).

---

## 5. Что проверено и претензий нет

- **SQL-инъекции** — весь доступ через ORM с параметризацией; `escape_like` (`crud.py:26-33`) корректно экранирует `%`, `_`, `\` перед `ilike`; `init.sh` использует psql-переменную `:'app_pw'` с автоквотированием. Единственный конкатенированный SQL — `ensure_schema`, но там имена из констант.
- **Path traversal в `/uploads/{filename}`** — двойная защита: `filename != Path(filename).name` + проверка HMAC (`main.py:1239-1250`).
- **Аутентификация покрывает все эндпоинты**, кроме намеренно публичных (`/health`, `/register`, `/login`, `/token`, `/uploads` с подписью, `admin/*` с `X-Admin-Token`).
- **Проверка владения объектом** корректна везде, кроме C-1: задачи, приёмы пищи, фото приёмов, замеры, тренировки — всё фильтруется по `user_id`.
- **Хеширование паролей** — bcrypt с корректной обрезкой до 72 байт и `gensalt()`.
- **Инвалидация токенов** через `token_version` при смене пароля — сделано правильно, включая проверку в `get_current_user` и в refresh-ветке.
- **Guard на дефолтные секреты** (`config.py:184-225`) — приложение не стартует с placeholder `SECRET_KEY` или словарным паролем БД. Хорошее решение.
- **Загрузка файлов** — extension allowlist + запись во временный файл с контролем размера + `PIL.verify()` + переименование в UUID + `os.replace` атомарно.
- **Пагинация** клэмпится (`main.py:692-693`, `crud.py:773, 829`) — `?limit=1000000` не выгрузит таблицу.
- **Фото не раздаются публичной статикой** — только по подписанным ссылкам с TTL.
- **`/docs` выключается в проде** через `ENABLE_DOCS`.
- **Целостность расчётов** — суммы КБЖУ составных блюд считаются на бэкенде, фронтовым суммам не доверяют (`crud.py:453`).
- **N+1 в дневнике** решён через `selectinload` (`crud.py:558-566`).
- **Circuit breaker** на ML-провайдерах и отдельный threadpool под LLM-советчика — грамотные решения.

---

## 6. Порядок работ

**Спринт 1 — блокеры релиза**
1. C-1 — проверка владения `task_id` в `POST /meals` (10 минут, дыра в приватности)
2. C-3 — `async def` → `def` на всех эндпоинтах с БД (механическая правка, максимальный эффект)
3. C-2 — убрать дубль `get_db`, пересчитать пул, поднять `max_connections`
4. H-3 — сузить `--forwarded-allow-ips`
5. H-1 — CSP в Caddyfile

**Спринт 2 — вместимость**
6. C-5 — задача очистки uploads + мониторинг диска
7. C-4 — выделенная очередь анализа, `--concurrency` вверх, лимиты
8. H-4 — rate-limit на `/advisor`, огрубление ключа кэша
9. H-5 — лимит мегапикселей
10. M-1 — pg_trgm индексы

**Спринт 3 — надёжность**
11. H-7 — Alembic вместо startup-DDL
12. H-2 — ротация refresh-токенов
13. H-6 — починить или удалить ретрейн
14. M-8 — не глотать ошибки анализа
15. Метрики + Sentry + нагрузочный тест (locust, сценарий: логин → дневник → добавление еды → анализ фото)

**Перед запуском на 5000 DAU обязательно проведите нагрузочный тест.** Расчёты выше — оценки; реальные цифры даст только прогон с профилем нагрузки, повторяющим пики приёмов пищи.
