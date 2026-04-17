#!/bin/bash
# Скрипт для поиска файла с синтаксической ошибкой на сервере

set -e

BOT_DIR="/opt/gptbot/app/bot"
VENV_PYTHON="/opt/gptbot/venv/bin/python3"

echo "🔍 Поиск файла с синтаксической ошибкой..."

# Проверяем все .py файлы в директории бота
find "$BOT_DIR" -name "*.py" -type f | while read -r file; do
    echo "Проверка: $file"
    if ! "$VENV_PYTHON" -m py_compile "$file" 2>&1; then
        echo ""
        echo "❌❌❌ ОШИБКА СИНТАКСИСА НАЙДЕНА В: $file ❌❌❌"
        echo ""
        "$VENV_PYTHON" -m py_compile "$file" 2>&1 | head -30
        echo ""
        echo "Показываю проблемные строки:"
        # Показываем строки вокруг ошибки
        "$VENV_PYTHON" -m py_compile "$file" 2>&1 | grep -E "line [0-9]+" | head -5
        exit 1
    fi
done

echo "✅ Все файлы проверены, синтаксических ошибок не найдено"

