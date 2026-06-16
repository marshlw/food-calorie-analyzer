#!/bin/bash
# Быстрый старт Docker

set -e

echo "🚀 AI Healthy Docker Setup"
echo "================================"

# Проверка Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен"
    exit 1
fi

# Меню
echo ""
echo "Выберите действие:"
echo "1. Разработка (docker-compose up)"
echo "2. Production (docker-compose-prod.yml up)"
echo "3. Только сборка образа"
echo "4. Остановить контейнеры"
echo "5. Удалить образ"
echo ""

read -p "Ввод (1-5): " choice

case $choice in
    1)
        echo "🔨 Запуск разработки..."
        docker-compose up -d
        echo "✅ Готово! API доступен на http://localhost:8000"
        echo "📝 Логи: docker-compose logs -f"
        ;;
    2)
        echo "🔨 Запуск production..."
        docker-compose -f docker-compose-prod.yml up -d
        echo "✅ Готово! API доступен на http://localhost:8000"
        echo "📝 Логи: docker-compose -f docker-compose-prod.yml logs -f"
        ;;
    3)
        echo "🔨 Сборка образа..."
        docker build -t ai-healthy:latest .
        echo "✅ Образ собран: ai-healthy:latest"
        docker images ai-healthy
        ;;
    4)
        echo "🛑 Остановка контейнеров..."
        docker-compose down
        echo "✅ Контейнеры остановлены"
        ;;
    5)
        echo "🗑️ Удаление образа..."
        docker rmi -f ai-healthy:latest
        echo "✅ Образ удален"
        ;;
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

echo ""
echo "📖 Больше информации: cat DOCKER.md"
