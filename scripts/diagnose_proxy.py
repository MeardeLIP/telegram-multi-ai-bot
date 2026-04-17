#!/usr/bin/env python3
"""
Скрипт для диагностики прокси на сервере.
Проверяет установку httpx-socks, настройки прокси и тестирует подключение.
"""
import os
import sys
import asyncio
from pathlib import Path

# Добавляем путь к проекту
project_dir = Path(__file__).parent.parent
sys.path.insert(0, str(project_dir))

def check_httpx_socks():
    """Проверяет установку httpx-socks."""
    print("=" * 60)
    print("1. ПРОВЕРКА УСТАНОВКИ httpx-socks")
    print("=" * 60)
    try:
        import httpx_socks
        version = getattr(httpx_socks, '__version__', 'unknown')
        print(f"✅ httpx-socks установлен")
        print(f"   Версия: {version}")
        print(f"   Путь: {httpx_socks.__file__}")
        return True, version
    except ImportError as e:
        print(f"❌ httpx-socks НЕ УСТАНОВЛЕН")
        print(f"   Ошибка: {e}")
        print(f"   Установите: pip install httpx-socks")
        return False, None

def check_proxy_config():
    """Проверяет настройки прокси в .env."""
    print("\n" + "=" * 60)
    print("2. ПРОВЕРКА НАСТРОЕК ПРОКСИ")
    print("=" * 60)
    
    env_file = project_dir / ".env"
    if not env_file.exists():
        print(f"⚠️ Файл .env не найден: {env_file}")
        return None
    
    proxy_url = None
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip().startswith('YOOKASSA_PROXY='):
                proxy_url = line.split('=', 1)[1].strip().strip('"').strip("'")
                break
    
    if proxy_url:
        # Маскируем пароль
        masked_proxy = proxy_url
        if "@" in proxy_url:
            parts = proxy_url.split("@")
            if len(parts) == 2:
                auth_part = parts[0]
                if "://" in auth_part:
                    scheme_user_pass = auth_part.split("://", 1)[1]
                    if ":" in scheme_user_pass:
                        user_pass = scheme_user_pass.split(":", 1)
                        if len(user_pass) == 2:
                            masked_proxy = f"{proxy_url.split('://')[0]}://{user_pass[0]}:****@{parts[1]}"
        
        print(f"✅ Прокси найден в .env")
        print(f"   Маскированный URL: {masked_proxy}")
        print(f"   Схема: {proxy_url.split('://')[0] if '://' in proxy_url else 'unknown'}")
        
        if "@" in proxy_url:
            host_port = proxy_url.split("@")[1]
            print(f"   Хост:порт: {host_port}")
        elif "://" in proxy_url:
            host_port = proxy_url.split("://")[1]
            if "@" in host_port:
                host_port = host_port.split("@")[1]
            print(f"   Хост:порт: {host_port}")
        
        return proxy_url
    else:
        print("❌ YOOKASSA_PROXY не найден в .env")
        return None

async def test_proxy_connection(proxy_url, socks5_available):
    """Тестирует подключение через прокси."""
    print("\n" + "=" * 60)
    print("3. ТЕСТИРОВАНИЕ ПОДКЛЮЧЕНИЯ ЧЕРЕЗ ПРОКСИ")
    print("=" * 60)
    
    if not proxy_url:
        print("⚠️ Прокси не настроен, пропускаем тест")
        return False
    
    import httpx
    
    # Маскируем пароль для логов
    masked_proxy = proxy_url
    if "@" in proxy_url:
        parts = proxy_url.split("@")
        if len(parts) == 2:
            auth_part = parts[0]
            if "://" in auth_part:
                scheme_user_pass = auth_part.split("://", 1)[1]
                if ":" in scheme_user_pass:
                    user_pass = scheme_user_pass.split(":", 1)
                    if len(user_pass) == 2:
                        masked_proxy = f"{proxy_url.split('://')[0]}://{user_pass[0]}:****@{parts[1]}"
    
    print(f"Прокси: {masked_proxy}")
    print(f"Тестируем подключение к YooKassa API...")
    
    transport = None
    if proxy_url.startswith("socks5://"):
        if not socks5_available:
            print("❌ SOCKS5 прокси требует httpx-socks, но он не установлен")
            return False
        
        try:
            from httpx_socks import AsyncProxyTransport
            transport = AsyncProxyTransport.from_url(proxy_url)
            print("✅ SOCKS5 транспорт создан")
        except Exception as e:
            print(f"❌ Ошибка создания SOCKS5 транспорта: {e}")
            return False
    else:
        try:
            transport = httpx.AsyncHTTPTransport(proxy=proxy_url, verify=False)
            print("✅ HTTP/HTTPS транспорт создан")
        except Exception as e:
            print(f"❌ Ошибка создания HTTP транспорта: {e}")
            return False
    
    # Тестируем подключение
    test_url = "https://api.yookassa.ru/v3"
    print(f"Отправка тестового запроса к: {test_url}")
    
    try:
        async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
            response = await client.get(test_url)
            print(f"✅ Подключение успешно!")
            print(f"   Статус: {response.status_code}")
            print(f"   Заголовки: {dict(list(response.headers.items())[:5])}")
            return True
    except httpx.TimeoutException as e:
        print(f"❌ Таймаут при подключении: {e}")
        print(f"   Прокси может быть недоступен или слишком медленный")
        return False
    except httpx.ConnectError as e:
        print(f"❌ Ошибка подключения: {e}")
        error_str = str(e)
        if "Connection refused" in error_str or "refused" in error_str.lower():
            print(f"   → Прокси отказывает в подключении")
            print(f"   → Проверьте доступность прокси и правильность логина/пароля")
        elif "name resolution" in error_str.lower():
            print(f"   → Не удается разрешить имя прокси сервера")
        return False
    except Exception as e:
        print(f"❌ Неожиданная ошибка: {type(e).__name__}: {e}")
        return False

def main():
    """Основная функция диагностики."""
    print("\n" + "🔍" * 30)
    print("ДИАГНОСТИКА ПРОКСИ ДЛЯ YOOKASSA")
    print("🔍" * 30 + "\n")
    
    # 1. Проверка httpx-socks
    socks5_available, socks5_version = check_httpx_socks()
    
    # 2. Проверка настроек прокси
    proxy_url = check_proxy_config()
    
    # 3. Тестирование подключения
    if proxy_url:
        result = asyncio.run(test_proxy_connection(proxy_url, socks5_available))
        
        print("\n" + "=" * 60)
        print("ИТОГИ ДИАГНОСТИКИ")
        print("=" * 60)
        print(f"httpx-socks: {'✅ Установлен' if socks5_available else '❌ Не установлен'}")
        if socks5_available and socks5_version:
            print(f"   Версия: {socks5_version}")
        print(f"Прокси настроен: {'✅ Да' if proxy_url else '❌ Нет'}")
        if proxy_url:
            scheme = proxy_url.split("://")[0] if "://" in proxy_url else "unknown"
            print(f"   Схема: {scheme}")
        print(f"Тест подключения: {'✅ Успешно' if result else '❌ Не удалось'}")
        
        if not result:
            print("\n⚠️ РЕКОМЕНДАЦИИ:")
            if proxy_url.startswith("socks5://") and not socks5_available:
                print("   1. Установите httpx-socks: pip install httpx-socks")
            print("   2. Проверьте доступность прокси сервера")
            print("   3. Проверьте правильность логина/пароля")
            print("   4. Проверьте логи API сервера для детальной информации")
    else:
        print("\n⚠️ Прокси не настроен, диагностика неполная")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()

