#!/usr/bin/env python3
"""Финальная проверка работы сервера."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD)

print("🔍 Финальная проверка сервера")
print("="*60)

time.sleep(3)

# Статус сервисов
print("\n📊 Статус сервисов:")
stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service gptbot-bot.service --no-pager | head -n 20')
print(stdout.read().decode('utf-8'))

# Проверка ошибок
print("\n🔍 Проверка ошибок в логах:")
stdin, stdout, stderr = ssh.exec_command('journalctl -u gptbot-api.service -u gptbot-bot.service --since "2 minutes ago" --no-pager | grep -i error | tail -n 5')
errors = stdout.read().decode('utf-8')
print(errors if errors.strip() else "✓ Ошибок не найдено")

# Проверка последних логов бота
print("\n🔍 Последние логи бота:")
stdin, stdout, stderr = ssh.exec_command('journalctl -u gptbot-bot.service --since "2 minutes ago" --no-pager | tail -n 15')
bot_logs = stdout.read().decode('utf-8')
print(bot_logs if bot_logs.strip() else "Логи пусты")

# Проверка API
print("\n🔍 Проверка API:")
stdin, stdout, stderr = ssh.exec_command('curl -s http://localhost:8000/health')
health = stdout.read().decode('utf-8')
print(f"Health check: {health.strip()}")

ssh.close()

print("\n✅ Проверка завершена!")

