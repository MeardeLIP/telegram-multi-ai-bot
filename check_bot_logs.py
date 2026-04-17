#!/usr/bin/env python3
"""Проверка логов бота на сервере для диагностики проблемы с кнопками."""
import paramiko

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_DIR = "/opt/gptbot"

password = input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(SERVER_IP, username=SERVER_USER, password=password, timeout=10)
    print("✓ Подключено\n")
    
    # Проверяем статус сервиса
    print("=" * 60)
    print("📊 СТАТУС СЕРВИСА GPTBOT-BOT")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("systemctl status gptbot-bot.service --no-pager -l -n 20")
    print(stdout.read().decode('utf-8'))
    
    # Последние логи
    print("\n" + "=" * 60)
    print("📋 ПОСЛЕДНИЕ ЛОГИ (100 строк)")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("journalctl -u gptbot-bot.service -n 100 --no-pager")
    print(stdout.read().decode('utf-8'))
    
    # Поиск ошибок
    print("\n" + "=" * 60)
    print("🔍 ПОИСК ОШИБОК (callback, error, exception, traceback)")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("journalctl -u gptbot-bot.service -n 200 --no-pager | grep -iE 'error|exception|traceback|callback|failed'")
    output = stdout.read().decode('utf-8')
    if output.strip():
        print(output)
    else:
        print("Ошибок не найдено")
    
    # Проверяем статус API сервиса тоже
    print("\n" + "=" * 60)
    print("📊 СТАТУС СЕРВИСА GPTBOT-API")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("systemctl status gptbot-api.service --no-pager -l -n 20")
    print(stdout.read().decode('utf-8'))
    
    # Логи API для диагностики Connection refused
    print("\n" + "=" * 60)
    print("📋 ПОСЛЕДНИЕ ЛОГИ API (50 строк)")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("journalctl -u gptbot-api.service -n 50 --no-pager")
    print(stdout.read().decode('utf-8'))
    
    # Проверка доступности API локально
    print("\n" + "=" * 60)
    print("🌐 ПРОВЕРКА ДОСТУПНОСТИ API НА СЕРВЕРЕ")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("curl -s http://localhost:8000/health || echo 'API недоступен на localhost:8000'")
    print(stdout.read().decode('utf-8'))
    
    # Проверка на 127.0.0.1 тоже
    stdin, stdout, stderr = ssh.exec_command("curl -s http://127.0.0.1:8000/health || echo 'API недоступен на 127.0.0.1:8000'")
    print(stdout.read().decode('utf-8'))
    
    # Проверка что слушает на порту 8000
    print("\n" + "=" * 60)
    print("🔌 ПРОВЕРКА ПОРТА 8000")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command("netstat -tlnp | grep :8000 || ss -tlnp | grep :8000 || echo 'Порт 8000 не найден'")
    print(stdout.read().decode('utf-8'))
    
    # Проверка переменной API_INTERNAL_URL в .env
    print("\n" + "=" * 60)
    print("⚙️ ПРОВЕРКА API_INTERNAL_URL В .ENV")
    print("=" * 60)
    stdin, stdout, stderr = ssh.exec_command(f"grep -E '^API_INTERNAL_URL|^api_internal_url' {SERVER_DIR}/.env 2>/dev/null || echo 'API_INTERNAL_URL не найден в .env'")
    print(stdout.read().decode('utf-8'))
    
    # Проверка прокси для OpenAI
    print("\n" + "=" * 60)
    print("🔍 ПРОВЕРКА ПРОКСИ ДЛЯ OPENAI")
    print("=" * 60)
    # Получаем значение OPENAI_PROXY из .env
    stdin, stdout, stderr = ssh.exec_command(f"grep -E '^OPENAI_PROXY=' {SERVER_DIR}/.env 2>/dev/null | cut -d'=' -f2- || echo ''")
    proxy_value = stdout.read().decode('utf-8').strip()
    
    if proxy_value:
        print(f"Найден прокси: {proxy_value[:50]}..." if len(proxy_value) > 50 else f"Найден прокси: {proxy_value}")
        print("\nПроверка доступности OpenAI API через прокси...")
        # Тестируем подключение к OpenAI API через прокси
        test_cmd = f"curl -s -o /dev/null -w 'HTTP Status: %{{http_code}}, Time: %{{time_total}}s\\n' --connect-timeout 10 --max-time 15 --proxy '{proxy_value}' https://api.openai.com/v1/models -H 'Authorization: Bearer test' 2>&1 || echo 'ОШИБКА: Прокси не работает'"
        stdin, stdout, stderr = ssh.exec_command(test_cmd)
        result = stdout.read().decode('utf-8')
        if 'HTTP Status: 401' in result or 'HTTP Status: 200' in result:
            print("✅ Прокси РАБОТАЕТ (OpenAI API доступен через прокси)")
        elif 'HTTP Status: 000' in result or 'ОШИБКА' in result or 'timeout' in result.lower():
            print("❌ Прокси НЕ РАБОТАЕТ (не удается подключиться через прокси)")
            print(f"Детали: {result}")
        else:
            print(f"⚠️ Неопределенный результат: {result}")
    else:
        print("⚠️ OPENAI_PROXY не настроен в .env")
        print("Проверка прямого доступа к OpenAI API...")
        # Проверяем прямой доступ (без прокси)
        stdin, stdout, stderr = ssh.exec_command("curl -s -o /dev/null -w 'HTTP Status: %{http_code}, Time: %{time_total}s\\n' --connect-timeout 10 --max-time 15 https://api.openai.com/v1/models -H 'Authorization: Bearer test' 2>&1")
        result = stdout.read().decode('utf-8')
        if 'HTTP Status: 401' in result or 'HTTP Status: 200' in result:
            print("✅ OpenAI API доступен БЕЗ прокси (прямое подключение работает)")
        elif 'HTTP Status: 000' in result or 'timeout' in result.lower() or 'Connection refused' in result:
            print("❌ OpenAI API НЕ доступен БЕЗ прокси (нужен прокси)")
            print(f"Детали: {result}")
        else:
            print(f"Результат: {result}")
    
    # Проверка что файлы обновлены
    print("\n" + "=" * 60)
    print("📁 ПРОВЕРКА ДАТЫ МОДИФИКАЦИИ ФАЙЛОВ")
    print("=" * 60)
    files_to_check = [
        "app/bot/main.py",
        "app/bot/handlers/profile.py",
        "app/bot/handlers/admin.py",
        "app/bot/handlers/promo_admin.py",
    ]
    for file_path in files_to_check:
        stdin, stdout, stderr = ssh.exec_command(f"stat -c '%y %n' {SERVER_DIR}/{file_path} 2>/dev/null || echo 'Файл не найден: {file_path}'")
        print(stdout.read().decode('utf-8').strip())
    
except Exception as e:
    print(f"✗ Ошибка: {e}")
finally:
    ssh.close()

