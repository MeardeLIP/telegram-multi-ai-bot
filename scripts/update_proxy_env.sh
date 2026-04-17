#!/bin/bash
# Скрипт для обновления YOOKASSA_PROXY в .env на сервере

set -e

ENV_FILE="/opt/gptbot/.env"
# ВАЖНО: используем SOCKS5 для поддержки HTTPS туннелирования
# SOCKS5 прокси поддерживает как HTTP, так и HTTPS запросы
PROXY_URL="socks5://hUz7QC:Pt4Jk4@45.143.245.65:8000"

echo "🔧 Обновление YOOKASSA_PROXY в .env..."

# Создаём .env если его нет
if [ ! -f "$ENV_FILE" ]; then
    echo "⚠ Файл .env не найден, создаю новый..."
    touch "$ENV_FILE"
fi

# Удаляем старую строку YOOKASSA_PROXY если есть
if grep -q "^YOOKASSA_PROXY=" "$ENV_FILE"; then
    sed -i '/^YOOKASSA_PROXY=/d' "$ENV_FILE"
    echo "✓ Удалена старая строка YOOKASSA_PROXY"
fi

# Добавляем новую строку YOOKASSA_PROXY
echo "YOOKASSA_PROXY=$PROXY_URL" >> "$ENV_FILE"
echo "✓ Добавлена новая строка YOOKASSA_PROXY=$PROXY_URL"

# Убеждаемся что нет дубликатов
sort -u "$ENV_FILE" -o "$ENV_FILE".tmp && mv "$ENV_FILE".tmp "$ENV_FILE"

echo ""
echo "✅ YOOKASSA_PROXY обновлён в .env"
echo "📋 Текущее значение:"
grep "^YOOKASSA_PROXY=" "$ENV_FILE" || echo "⚠ YOOKASSA_PROXY не найден в .env"

