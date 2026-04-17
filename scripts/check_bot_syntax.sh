#!/bin/bash
# Скрипт для проверки синтаксиса Python файлов бота на сервере

set -e

BOT_DIR="/opt/gptbot/app/bot"

echo "🔍 Проверка синтаксиса Python файлов бота..."

# Проверяем все .py файлы в директории бота
find "$BOT_DIR" -name "*.py" -type f | while read -r file; do
    echo "Проверка: $file"
    python3 -m py_compile "$file" 2>&1 || {
        echo "❌ ОШИБКА СИНТАКСИСА В: $file"
        python3 -m py_compile "$file" 2>&1 | head -20
        exit 1
    }
done

echo "✅ Все файлы проверены, синтаксических ошибок не найдено"

