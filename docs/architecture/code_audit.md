# Code Audit

> Переписано с нуля по факту чтения кода. Предыдущая версия этого файла описывала
> несуществующую структуру пакета, несуществующие `Dockerfile`/`docker-compose.yml`/
> `requirements.txt`, вымышленные версии зависимостей и результаты прогона тестов — доверять
> ей было нельзя. Здесь — только проверенные наблюдения по состоянию репозитория на дату
> последнего обновления этого файла.

## Package Structure (факт)

Реализация — **плоский пакет `app/`**: `app/main.py`, `app/models.py`, `app/schemas.py`,
`app/crud.py`, `app/auth.py`, `app/config.py`, `app/database.py`, `app/ml_service.py`,
`app/advisor.py`, `app/tasks.py`, `app/celery_app.py`, `app/telegram_bot.py`, `app/api_client.py`,
`app/rate_limit.py`, `app/utils.py`, `app/barcode_service.py`, `app/protein_source.py`,
`app/food_map.py`, `app/seed_products.py`, `app/seed_exercises.py`. Никакого «двухуровневого
proxy-паттерна» (`app/` re-export из `app/app/`) не существует — `app/app/` содержит только
`tests/`, `uploads/` (файлы пользователей), `training_data/` и `__pycache__`, не код приложения.

## ML Service (`app/ml_service.py`)

Четыре реально реализованных и рабочих провайдера: `GeminiProvider`, `DeepSeekProvider`,
`OllamaProvider`, `YandexProvider`. Порядок фолбэка **не фиксирован в коде** — вычисляется
`get_provider_callables()` из `settings.MODEL_PROVIDER` (по умолчанию `"yandex"`): предпочтённый
провайдер идёт первым, остальные три — в порядке `gemini, deepseek, ollama` за вычетом уже
поставленного первым. Т.е. при значении по умолчанию цепочка — **yandex → gemini → deepseek →
ollama**, а не «Gemini → DeepSeek → Ollama», как утверждала предыдущая версия этого документа.
Каждый провайдер обёрнут в `CircuitBreaker` (3 подряд неудачи → 300 c отключения) и повторяет
попытку до `MODEL_RETRY_ATTEMPTS` (2) раз с задержкой.

**Мёртвый код:**
- `MODEL_CANDIDATES` (список имён моделей Gemini, строки 117–121) нигде не используется.
- Функция `rate_limit()` (троттлинг per-provider, `time.sleep`) определена, но **не вызывается**
  ни в одном провайдере и ни в `analyze_image_sync` — не путать с активно используемым модулем
  `app/rate_limit.py` (совсем другой код: брутфорс-защита логина, дневные лимиты AI/штрих-кодов/
  советчика — используется в `main.py` повсеместно и работает).

**Кэш:** ключ `f"{settings.CACHE_PREFIX}:{PROMPT_VERSION}:{get_hash(path)}"` (по умолчанию
`food_analysis:v4:v15:<sha256>`), TTL = `CACHE_TTL` (24 ч).

## Известные несоответствия и незавершённые куски

- **`training_data/generate_dataset.py` сломан относительно текущего конфига:** обращается к
  `settings.MODEL_NAME`, которого больше нет в `app/config.py` (текущая конфигурация — `MODEL_PROVIDER`
  + `YANDEX_*`/`GEMINI_*`/`OLLAMA_*` per-provider поля). Это означает, что `retrain_model_task`
  (Celery-задача переобучения, запускаемая из `crud.create_feedback_sync` при накоплении ≥10
  необработанных фидбеков — см. [бизнес-правила](../requirements/business-rules.md) BR-21)
  упадёт при попытке выполниться. Переобучение через Ollama сейчас нефункционально; чтобы
  почистить долг, либо чинить `generate_dataset.py` под текущий конфиг, либо выключать
  автозапуск переобучения и явно документировать фичу как отключённую.
- **`crud.learn_products_from_feedback`** — функция, дописывающая в справочник `products`
  «изученные» из фидбеков продукты с грубой оценкой КБЖУ, — намеренно **не вызывается** нигде
  (закомментированный/неиспользуемый путь), с комментарием в коде не включать её без реальных
  данных о нутриентах. Это осознанное решение, не баг.
- **`docker-compose.yml`/`docker-compose-prod.yml` отсутствуют в репозитории** — при этом
  `Dockerfile`, `requirements.txt`, `.dockerignore` и `.gitignore` **есть** в корне и в целом
  соответствуют тому, что описывает [`docs/setup/DOCKER.md`](../setup/DOCKER.md) (multi-stage
  сборка: Node 18 для фронтенда → Python 3.10-slim-bullseye для бэкенда). `docker build -t
  ai-healthy .` должен работать уже сейчас; не хватает только compose-файлов для оркестрации
  (db/redis/celery/ollama вместе) — DOCKER.md обновлён с пометкой об этом и добавлен запасной
  раздел «Локальный запуск без Docker».
- **`docs/api/swagger.yaml` существует** и был точным для более раннего, меньшего набора
  эндпоинтов — дополнен в этом обновлении недостающими путями (`/analyze/limit`, `/products`,
  `/barcode/*`, `/workouts/*`, `/exercises`, `/advisor/*`, фото приёма пищи, `/change-password`,
  `/profile/weight/{id}`) и полями схем (разделение белка животный/растительный, `custom_*`
  нормы, обхваты тела).
- **Postman-коллекция (`docs/api/postman-collection.json`) была неполной** (26 запросов, те же
  пропуски, что и в swagger.yaml выше) — дополнена до 40 запросов в этом обновлении, см.
  [POSTMAN_README](../api/POSTMAN_README.md).
- **Дублирующая устаревшая Postman-коллекция в корне репозитория:**
  `AI-Healthy-API-Collection.postman_collection.json` + `AI-Healthy-Environment.postman_environment.json`
  (17 эндпоинтов, часть контрактов не совпадает с текущим кодом — например, `Login` через
  `application/x-www-form-urlencoded`, статусы фидбека `approved/rejected` вместо реальных
  `pending/used`). Полностью перекрывается `docs/api/postman-collection.json`; помечена как
  мусор к удалению (см. ниже).
- **Telegram-бот, кнопка «🚪 Выйти»:** в клавиатуре присутствует, но явного обработчика для неё в
  `app/telegram_bot.py` на момент аудита не найдено — вероятно, no-op (сообщение не будет
  обработано ни одним хендлером). Стоит перепроверить при следующей правке бота.

## Безопасность — что уже сделано правильно

(Предыдущая версия документа рекомендовала часть из этого как «TODO» — на деле уже реализовано.)

- CORS ограничен явным списком `settings.ALLOWED_ORIGINS` (не `["*"]`).
- `SECRET_KEY` берётся из окружения; `Settings.model_post_init` **отказывает в старте**
  приложения, если ключ похож на плейсхолдер (`change-this`, `secret-key`, `12345` и т.п.),
  если явно не выставлен `ALLOW_INSECURE_SECRET_KEY=true` (для локальной разработки).
- Смена пароля инвалидирует все ранее выданные токены (`token_version`, см.
  [auth_flow.md](auth_flow.md)).
- Пароли Telegram-аккаунтов — случайный секрет в Redis, а не предсказуемый Telegram ID
  (с миграцией старых аккаунтов) — см. [auth_flow.md](auth_flow.md) «Bot specifics».
- Файлы `/uploads/{filename}` не раздаются публично — только по HMAC-подписанной ссылке с TTL.
- Admin-эндпоинты полностью отключаются (`404`), если `ADMIN_TOKEN` не задан или оставлен
  значением по умолчанию — не «защищены общеизвестным токеном», а выключены.

## Модернизация (не баги, но стоит знать)

- `app/main.py` использует `@app.on_event("startup"/"shutdown")` — в текущих версиях FastAPI это
  работает, но официально считается устаревшим паттерном в пользу `lifespan`-хендлеров.
- `app/tasks.py` использует `datetime.utcnow()` — в новых версиях Python помечено как
  deprecated в пользу `datetime.now(timezone.utc)`; функционально пока корректно.
- Валидация в `app/ml_service.py` (`IngredientItem`, `AnalysisResult`) использует Pydantic v1
  стиль `@validator` (а не `@field_validator` из Pydantic v2) — работает через
  совместимый режим, но не идиоматично для текущей версии Pydantic.

## Тесты

В репозитории есть тестовый набор: `app/app/tests/test_api.py`, `test_ml_service.py`,
`test_ml_contract.py`, `test_profile.py`, `test_telegram_bot.py`, `conftest.py`. В этой сессии
не было доступа к shell-окружению для запуска `pytest`, поэтому актуальный статус
прохождения тестов **не подтверждён** — не доверяйте старым числам («25 passed, 1 skipped»),
они не были перепроверены и, вероятно, устарели вместе с остальным этим файлом. Перед релизом
прогоните `pytest app/app/tests -v` локально.

## Мусорные/неактуальные файлы (устранено в рамках этого обновления)

- `main.dart` в корне репозитория — обрывок нерабочего Flutter-прототипа, не связанный с текущим
  React-фронтендом; удалён.
- `training_data/` (5 фото + `annotations.jsonl`) — крошечный датасет для нерабочего пайплайна
  переобучения (см. выше); удалён по решению владельца проекта.
- `app/app/uploads/` (246 файлов) — фото пользователей; удалены по явному решению владельца
  проекта (лишает существующие записи дневника превью фото — см. историю чата/коммитов).
- Корневые `AI-Healthy-API-Collection.postman_collection.json` +
  `AI-Healthy-Environment.postman_environment.json` — устаревший дубликат, полностью перекрытый
  `docs/api/postman-collection.json`; удалены.
- `.venv/` — Python-окружение (~1800 файлов), не должно лежать в репозитории; удалено по решению
  владельца проекта, восстанавливается через `pip install -r requirements.txt`.
- Артефакты кэшей (`__pycache__`, `.pytest_cache` ×2, `.git/.MERGE_MSG.swp`) — регенерируемый
  мусор, безопасно удалён.
- `.gitignore` в репозитории уже был, но не покрывал `node_modules/`, `.pytest_cache/` и реальный
  путь `app/app/uploads/` (в нём числился несуществующий `app/uploads/`) — дополнен.

## Рекомендованный план (актуализировано)

1. Добавить `docker-compose.yml` (dev) и, при необходимости, `docker-compose-prod.yml` — сам
   `Dockerfile`/`requirements.txt` уже в порядке, не хватает только оркестрации сервисов.
2. Почистить/удалить нерабочий пайплайн переобучения (`generate_dataset.py` + `retrain_model_task`)
   или починить ссылку на конфиг.
3. Прогнать `pytest` и обновить этот раздел реальными цифрами.
4. Убрать мёртвый код в `ml_service.py` (`MODEL_CANDIDATES`, неиспользуемый `rate_limit()`).
5. Проверить/удалить кнопку «Выйти» в Telegram-боте или добавить обработчик.
6. Держать `docs/api/swagger.yaml` и `docs/api/postman-collection.json` в синхроне при добавлении
   новых эндпоинтов — оба обновлены в этой сессии, но ручное обновление такого рода легко
   забыть; стоит рассмотреть генерацию Postman-коллекции из живого `/openapi.json`.
