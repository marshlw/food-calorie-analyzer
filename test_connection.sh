#!/bin/bash
# Скрипт для проверки соединения между telegram_bot и API контейнерами

echo "🔍 Проверка соединения между telegram_bot и API..."
echo ""

# Проверить, запущены ли контейнеры
echo "1️⃣ Проверка статуса контейнеров:"
docker-compose ps
echo ""

# Проверить соединение с API из telegram_bot контейнера
echo "2️⃣ Проверка соединения telegram_bot → API:"
docker-compose exec -T telegram_bot curl -s -o /dev/null -w "HTTP Status: %{http_code}\n" http://api:8000/health
echo ""

# Проверить соединение с Redis из telegram_bot контейнера
echo "3️⃣ Проверка соединения telegram_bot → Redis:"
docker-compose exec -T telegram_bot redis-cli -h redis ping
echo ""

# Показать логи telegram_bot
echo "4️⃣ Последние 20 строк логов telegram_bot:"
docker-compose logs --tail=20 telegram_bot
echo ""

echo "✅ Проверка завершена!"
