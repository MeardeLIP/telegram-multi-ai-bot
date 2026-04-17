#!/usr/bin/env python3
"""Обновление ADMIN_IDS в .env на сервере."""
import paramiko
import re

SERVER_IP = "149.33.0.41"
SERVER_USER = "root"
SERVER_DIR = "/opt/gptbot"
NEW_ADMIN_ID = "356142844"

password = input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    ssh.connect(SERVER_IP, username=SERVER_USER, password=password, timeout=10)
    print("✓ Подключено\n")
    
    env_path = f"{SERVER_DIR}/.env"
    
    # Читаем текущий .env
    print("📖 Чтение .env файла...")
    sftp = ssh.open_sftp()
    try:
        with sftp.open(env_path, 'r') as f:
            env_content = f.read().decode('utf-8')
    except FileNotFoundError:
        print(f"✗ Файл {env_path} не найден!")
        exit(1)
    finally:
        sftp.close()
    
    # Обновляем ADMIN_IDS
    print("✏️ Обновление ADMIN_IDS...")
    if re.search(r'^ADMIN_IDS=', env_content, re.MULTILINE):
        # Заменяем существующую строку
        env_content = re.sub(
            r'^ADMIN_IDS=.*$',
            f'ADMIN_IDS={NEW_ADMIN_ID}',
            env_content,
            flags=re.MULTILINE
        )
        print(f"✓ ADMIN_IDS обновлен на {NEW_ADMIN_ID}")
    else:
        # Добавляем новую строку в конец
        env_content += f"\nADMIN_IDS={NEW_ADMIN_ID}\n"
        print(f"✓ ADMIN_IDS добавлен: {NEW_ADMIN_ID}")
    
    # Записываем обновленный .env
    print("💾 Запись .env файла...")
    sftp = ssh.open_sftp()
    with sftp.open(env_path, 'w') as f:
        f.write(env_content.encode('utf-8'))
    sftp.close()
    print("✓ .env файл обновлен")
    
    # Перезапускаем сервисы
    print("\n🔄 Перезапуск сервисов...")
    stdin, stdout, stderr = ssh.exec_command(
        "systemctl restart gptbot-api.service gptbot-bot.service && "
        "sleep 2 && "
        "systemctl status gptbot-bot.service --no-pager -l -n 10"
    )
    
    output = stdout.read().decode('utf-8')
    print(output)
    
    print("\n✅ ADMIN_IDS обновлен и сервисы перезапущены!")
    
except Exception as e:
    print(f"✗ Ошибка: {e}")
    import traceback
    traceback.print_exc()
finally:
    ssh.close()

