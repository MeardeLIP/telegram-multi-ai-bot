#!/usr/bin/env python3
"""Проверка кода webhook на сервере."""
import paramiko

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD, timeout=30, allow_agent=False, look_for_keys=False)

print("🔍 Проверка кода webhook на сервере...")
print("="*60)

# Проверяем наличие user_tg_id
stdin, stdout, stderr = ssh.exec_command('grep -n "user_tg_id" /opt/gptbot/app/api/main.py | head -n 5')
result = stdout.read().decode('utf-8')
if result:
    print("✅ Найдено использование user_tg_id:")
    print(result)
else:
    print("❌ user_tg_id не найден в коде!")

# Проверяем функцию _mark_paid_and_apply
print("\n🔍 Проверка функции _mark_paid_and_apply...")
stdin, stdout, stderr = ssh.exec_command('grep -A 10 "async def _mark_paid_and_apply" /opt/gptbot/app/api/main.py | head -n 12')
result = stdout.read().decode('utf-8')
print(result)

ssh.close()

