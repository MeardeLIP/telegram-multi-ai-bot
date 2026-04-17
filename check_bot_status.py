#!/usr/bin/env python3
"""Детальная проверка статуса бота."""
import paramiko

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD)

import time
time.sleep(5)  # Ждем завершения перезапуска

print("🔍 Детальная проверка бота")
print("="*60)

# Статус сервиса
print("\n📊 Статус сервиса бота:")
stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-bot.service --no-pager -l')
print(stdout.read().decode('utf-8'))

# Последние 50 строк логов
print("\n📋 Последние 50 строк логов бота:")
stdin, stdout, stderr = ssh.exec_command('journalctl -u gptbot-bot.service -n 50 --no-pager')
logs = stdout.read().decode('utf-8')
print(logs)

# Проверка наличия BOT_TOKEN
print("\n🔑 Проверка BOT_TOKEN в .env:")
stdin, stdout, stderr = ssh.exec_command('grep "^BOT_TOKEN=" /opt/gptbot/.env | head -n 1')
token_line = stdout.read().decode('utf-8').strip()
if token_line:
    if 'your_bot_token' in token_line or 'your_' in token_line or not token_line.split('=')[1]:
        print("❌ BOT_TOKEN не настроен или содержит placeholder!")
        print(f"   {token_line.split('=')[0]}=****")
    else:
        print("✓ BOT_TOKEN настроен")
        print(f"   {token_line.split('=')[0]}=****")
else:
    print("❌ BOT_TOKEN не найден в .env!")

# Проверка ошибок
print("\n❌ Все ошибки в логах:")
stdin, stdout, stderr = ssh.exec_command('journalctl -u gptbot-bot.service --since "10 minutes ago" --no-pager | grep -iE "(error|exception|traceback|failed)" | tail -n 20')
errors = stdout.read().decode('utf-8')
if errors.strip():
    print(errors)
else:
    print("Ошибок не найдено")

# Проверка процесса
print("\n🔍 Проверка процесса бота:")
stdin, stdout, stderr = ssh.exec_command('ps aux | grep "app.bot.main" | grep -v grep')
process = stdout.read().decode('utf-8')
if process.strip():
    print("✓ Процесс бота запущен:")
    print(process)
else:
    print("❌ Процесс бота не найден!")

ssh.close()

