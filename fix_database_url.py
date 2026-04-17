#!/usr/bin/env python3
"""Исправление DATABASE_URL в .env."""
import paramiko

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(SERVER_IP, username=SERVER_USER, password=SERVER_PASSWORD)

print("🔧 Исправление DATABASE_URL в .env")
print("="*60)

# Читаем .env
sftp = ssh.open_sftp()
with sftp.file(f"{SERVER_DIR}/.env", 'r') as f:
    content = f.read().decode('utf-8')

# Исправляем DATABASE_URL
lines = content.split('\n')
new_lines = []
fixed = False

for line in lines:
    if line.startswith('DATABASE_URL='):
        if 'gptbot' in line:
            new_lines.append('DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app')
            print("✓ Исправлен DATABASE_URL: gptbot -> app")
            fixed = True
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

# Записываем обратно
with sftp.file(f"{SERVER_DIR}/.env", 'w') as f:
    f.write('\n'.join(new_lines))
sftp.close()

if fixed:
    print("\n🔄 Перезапуск сервисов...")
    ssh.exec_command('systemctl restart gptbot-api.service gptbot-bot.service')
    print("✓ Сервисы перезапущены")
    
    import time
    time.sleep(3)
    
    print("\n🔍 Проверка статуса...")
    stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-bot.service --no-pager | head -n 10')
    print(stdout.read().decode('utf-8'))
    
    print("\n🔍 Проверка ошибок в логах (последние 30 секунд)...")
    stdin, stdout, stderr = ssh.exec_command('journalctl -u gptbot-bot.service --since "30 seconds ago" --no-pager | grep -iE "(error|database)" | tail -n 5')
    errors = stdout.read().decode('utf-8')
    if errors.strip():
        print("⚠ Найдены ошибки:")
        print(errors)
    else:
        print("✓ Ошибок не найдено")
else:
    print("ℹ DATABASE_URL уже правильный")

ssh.close()
print("\n✅ Готово!")

