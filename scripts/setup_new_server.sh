#!/bin/bash
# Скрипт для первоначальной настройки нового Linux сервера
# Использование: bash setup_new_server.sh

set -e

echo "🚀 Настройка нового сервера для GPT Bot"
echo "========================================"

# Проверка, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ Ошибка: скрипт должен быть запущен от root"
    exit 1
fi

# Обновление системы
echo ""
echo "📦 Обновление системы..."
apt-get update
apt-get upgrade -y

# Установка системных зависимостей
echo ""
echo "📦 Установка системных зависимостей..."
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    postgresql \
    postgresql-contrib \
    redis-server \
    git \
    curl \
    wget \
    build-essential \
    libpq-dev \
    libssl-dev \
    libffi-dev

# Создание пользователя gptbot
echo ""
echo "👤 Создание пользователя gptbot..."
if ! id "gptbot" &>/dev/null; then
    useradd -m -s /bin/bash gptbot
    echo "✅ Пользователь gptbot создан"
else
    echo "⚠️ Пользователь gptbot уже существует"
fi

# Создание директории проекта
echo ""
echo "📁 Создание директории проекта..."
mkdir -p /opt/gptbot
chown gptbot:gptbot /opt/gptbot

# Настройка PostgreSQL
echo ""
echo "🗄️ Настройка PostgreSQL..."
sudo -u postgres psql -c "CREATE USER app WITH PASSWORD 'app';" 2>/dev/null || echo "⚠️ Пользователь app уже существует"
sudo -u postgres psql -c "CREATE DATABASE app OWNER app;" 2>/dev/null || echo "⚠️ База данных app уже существует"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE app TO app;"

# Настройка Redis
echo ""
echo "🔴 Настройка Redis..."
systemctl enable redis-server
systemctl start redis-server

# Создание виртуального окружения Python
echo ""
echo "🐍 Создание виртуального окружения Python..."
if [ ! -d "/opt/gptbot/venv" ]; then
    sudo -u gptbot python3.11 -m venv /opt/gptbot/venv
    echo "✅ Виртуальное окружение создано"
else
    echo "⚠️ Виртуальное окружение уже существует"
fi

echo ""
echo "✅ Настройка сервера завершена!"
echo ""
echo "Следующие шаги:"
echo "1. Скопируйте файлы проекта в /opt/gptbot"
echo "2. Создайте файл .env с настройками"
echo "3. Установите зависимости: cd /opt/gptbot && source venv/bin/activate && pip install -r requirements.txt"
echo "4. Примените миграции: python -m alembic upgrade head"
echo "5. Настройте systemd сервисы: cp scripts/gptbot-*.service /etc/systemd/system/"
echo "6. Запустите сервисы: systemctl enable --now gptbot-api.service gptbot-bot.service"

