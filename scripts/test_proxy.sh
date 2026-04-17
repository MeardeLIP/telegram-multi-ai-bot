#!/bin/bash
# Скрипт для тестирования прокси на сервере

echo "🔍 Тестирование прокси для YooKassa..."
echo ""

ENV_FILE="/opt/gptbot/.env"
PROXY_URL=""

# Читаем прокси из .env
if [ -f "$ENV_FILE" ]; then
    PROXY_URL=$(grep "^YOOKASSA_PROXY=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
fi

if [ -z "$PROXY_URL" ]; then
    echo "❌ Прокси не найден в .env файле"
    echo "Проверьте файл: $ENV_FILE"
    exit 1
fi

echo "📋 Найден прокси: ${PROXY_URL%%@*}@****"
echo ""

# Извлекаем хост и порт
if [[ $PROXY_URL =~ @([^:]+):([0-9]+) ]]; then
    PROXY_HOST="${BASH_REMATCH[1]}"
    PROXY_PORT="${BASH_REMATCH[2]}"
    echo "🔍 Хост прокси: $PROXY_HOST"
    echo "🔍 Порт прокси: $PROXY_PORT"
    echo ""
    
    # Тест TCP подключения
    echo "📡 Тест 1: TCP подключение к прокси..."
    if timeout 5 bash -c "echo > /dev/tcp/$PROXY_HOST/$PROXY_PORT" 2>/dev/null; then
        echo "✅ TCP подключение успешно"
    else
        echo "❌ TCP подключение не удалось"
        echo "   Прокси может быть недоступен или порт закрыт"
    fi
    echo ""
    
    # Тест HTTP подключения через curl
    echo "📡 Тест 2: HTTP подключение через прокси..."
    TEST_URL="https://api.yookassa.ru/v3"
    
    # Маскируем пароль для curl
    if [[ $PROXY_URL =~ (https?://)([^:]+):([^@]+)@(.+) ]]; then
        PROXY_SCHEME="${BASH_REMATCH[1]}"
        PROXY_USER="${BASH_REMATCH[2]}"
        PROXY_PASS="${BASH_REMATCH[3]}"
        PROXY_HOST_PORT="${BASH_REMATCH[4]}"
        
        echo "   Используется прокси: ${PROXY_SCHEME}${PROXY_USER}:****@${PROXY_HOST_PORT}"
        echo "   Тестируем подключение к: $TEST_URL"
        
        # Пробуем разные варианты curl
        echo "   Вариант 1: Прямой формат прокси URL..."
        if curl -s --proxy "$PROXY_URL" --proxy-insecure --max-time 10 "$TEST_URL" > /dev/null 2>&1; then
            echo "✅ HTTP подключение через прокси успешно (вариант 1)"
        else
            echo "   ❌ Вариант 1 не сработал"
            echo "   Вариант 2: Отдельные параметры прокси..."
            if curl -s --proxy "$PROXY_HOST_PORT" --proxy-user "$PROXY_USER:$PROXY_PASS" --proxy-insecure --max-time 10 "$TEST_URL" > /dev/null 2>&1; then
                echo "✅ HTTP подключение через прокси успешно (вариант 2)"
            else
                echo "   ❌ Вариант 2 не сработал"
                echo "   Проверьте логин/пароль и доступность прокси"
                echo "   Возможно прокси не поддерживает HTTPS туннелирование"
            fi
        fi
    else
        echo "⚠️ Не удалось распарсить прокси URL"
    fi
    echo ""
    
    # Тест через Python httpx из venv
    echo "📡 Тест 3: Тест через Python httpx из venv (как в коде)..."
    if [ -f "/opt/gptbot/venv/bin/python" ]; then
        /opt/gptbot/venv/bin/python << EOF
import asyncio
import httpx
import sys

async def test():
    try:
        proxy_url = "$PROXY_URL"
        print(f"   Прокси: {proxy_url.split('@')[0]}@****")
        
        transport = httpx.AsyncHTTPTransport(
            proxy=proxy_url,
            verify=False
        )
        
        async with httpx.AsyncClient(timeout=10.0, transport=transport) as client:
            response = await client.get("https://api.yookassa.ru/v3")
            print(f"   ✅ Успешно! Статус: {response.status_code}")
            return True
    except httpx.TimeoutException as e:
        print(f"   ❌ Таймаут: {e}")
        return False
    except httpx.ConnectError as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return False
    except Exception as e:
        print(f"   ❌ Ошибка: {type(e).__name__}: {e}")
        return False

result = asyncio.run(test())
sys.exit(0 if result else 1)
EOF

        if [ $? -eq 0 ]; then
            echo "✅ Python httpx тест успешен"
        else
            echo "❌ Python httpx тест не удался"
        fi
    else
        echo "⚠️ venv не найден, пропускаем Python тест"
        echo "   venv должен быть в /opt/gptbot/venv/"
    fi
    echo ""
    
    # Тест 4: Проверка через простой HTTP запрос (без HTTPS)
    echo "📡 Тест 4: Простой HTTP запрос через прокси (httpbin.org)..."
    if curl -s --proxy "$PROXY_URL" --max-time 10 "http://httpbin.org/ip" > /dev/null 2>&1; then
        echo "✅ HTTP запрос через прокси успешен"
        echo "   Прокси работает для HTTP, но может не поддерживать HTTPS туннелирование"
    else
        echo "❌ HTTP запрос через прокси не удался"
        echo "   Проблема с авторизацией или прокси не работает"
    fi
else
    echo "❌ Не удалось распарсить прокси URL"
    exit 1
fi

echo ""
echo "✅ Тестирование завершено"

