#!/bin/bash
# Скрипт автоматической настройки Ubuntu 22.04 сервера для Telegram бота
# Выполнять от имени root: bash setup_linux_server.sh

set -e  # Остановка при ошибке

echo "=========================================="
echo "  Настройка сервера для GPT Bot"
echo "=========================================="
echo

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Функция для вывода сообщений
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then 
    error "Пожалуйста, запустите скрипт от имени root (sudo bash setup_linux_server.sh)"
    exit 1
fi

info "Начинаем настройку сервера..."

# ==========================================
# ШАГ 1: Обновление системы
# ==========================================
info "Шаг 1/7: Обновление системы..."
apt update
apt upgrade -y
info "Система обновлена"

# ==========================================
# ШАГ 2: Установка базовых инструментов
# ==========================================
info "Шаг 2/7: Установка базовых инструментов..."
apt install -y \
    curl \
    wget \
    git \
    vim \
    nano \
    htop \
    net-tools \
    build-essential \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    gnupg \
    lsb-release
info "Базовые инструменты установлены"

# ==========================================
# ШАГ 3: Установка Python 3.11+
# ==========================================
info "Шаг 3/7: Установка Python 3.11+..."
apt install -y python3.11 python3.11-venv python3.11-dev python3-pip

# Создаем симлинк для python3 -> python3.11
if [ ! -f /usr/bin/python3 ]; then
    ln -s /usr/bin/python3.11 /usr/bin/python3
fi

# Обновляем pip
python3 -m pip install --upgrade pip setuptools wheel

info "Python установлен: $(python3 --version)"
info "pip установлен: $(python3 -m pip --version)"

# ==========================================
# ШАГ 4: Установка PostgreSQL
# ==========================================
info "Шаг 4/7: Установка PostgreSQL..."
apt install -y postgresql postgresql-contrib

# Запускаем PostgreSQL
systemctl start postgresql
systemctl enable postgresql

# Создаем пользователя и базу данных
info "Создание пользователя и базы данных PostgreSQL..."
sudo -u postgres psql <<EOF
-- Создаем пользователя
CREATE USER app WITH PASSWORD 'app';
ALTER USER app CREATEDB;

-- Создаем базу данных
CREATE DATABASE app OWNER app;

-- Выдаем права
GRANT ALL PRIVILEGES ON DATABASE app TO app;
\q
EOF

info "PostgreSQL установлен и настроен"
info "  Пользователь: app"
info "  Пароль: app"
info "  База данных: app"

# ==========================================
# ШАГ 5: Установка Redis
# ==========================================
info "Шаг 5/7: Установка Redis..."
apt install -y redis-server

# Настраиваем Redis
sed -i 's/^bind 127.0.0.1/bind 127.0.0.1 ::1/' /etc/redis/redis.conf
sed -i 's/^# maxmemory <bytes>/maxmemory 256mb/' /etc/redis/redis.conf
sed -i 's/^# maxmemory-policy noeviction/maxmemory-policy allkeys-lru/' /etc/redis/redis.conf

# Запускаем Redis
systemctl start redis-server
systemctl enable redis-server

info "Redis установлен и настроен"

# ==========================================
# ШАГ 6: Установка системных библиотек для Python пакетов
# ==========================================
info "Шаг 6/7: Установка системных библиотек для Python..."
apt install -y \
    libpq-dev \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libatlas-base-dev \
    gfortran \
    libopenblas-dev \
    liblapack-dev

info "Системные библиотеки установлены"

# ==========================================
# ШАГ 7: Создание пользователя и директории для бота
# ==========================================
info "Шаг 7/7: Создание окружения для бота..."

# Создаем пользователя для бота (если не существует)
if ! id -u gptbot &>/dev/null; then
    useradd -m -s /bin/bash gptbot
    info "Пользователь gptbot создан"
else
    info "Пользователь gptbot уже существует"
fi

# Создаем директорию для проекта
PROJECT_DIR="/opt/gptbot"
mkdir -p "$PROJECT_DIR"
chown gptbot:gptbot "$PROJECT_DIR"
info "Директория проекта создана: $PROJECT_DIR"

# ==========================================
# Проверка доступности сервисов
# ==========================================
info "Проверка доступности сервисов..."

# PostgreSQL
if systemctl is-active --quiet postgresql; then
    info "✓ PostgreSQL работает"
else
    error "✗ PostgreSQL не работает"
fi

# Redis
if systemctl is-active --quiet redis-server; then
    info "✓ Redis работает"
else
    error "✗ Redis не работает"
fi

# Проверка подключения к PostgreSQL
if sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    info "✓ PostgreSQL доступен"
else
    error "✗ PostgreSQL недоступен"
fi

# Проверка подключения к Redis
if redis-cli ping > /dev/null 2>&1; then
    info "✓ Redis доступен"
else
    error "✗ Redis недоступен"
fi

echo
echo "=========================================="
info "Настройка сервера завершена!"
echo "=========================================="
echo
info "Следующие шаги:"
echo "  1. Скопируйте код бота в $PROJECT_DIR"
echo "  2. Создайте .env файл с настройками"
echo "  3. Установите Python зависимости: pip install -r requirements.txt"
echo "  4. Примените миграции: alembic upgrade head"
echo "  5. Настройте systemd сервисы для автозапуска"
echo
info "Проверка доступности YooKassa и OpenAI:"
echo "  Выполните: bash check_services.sh"
echo

