#!/usr/bin/env python3
"""
Копирование .env файла на сервер и настройка прокси для OpenAI.
"""
import paramiko
import socket
import time
import os
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
PROJECT_DIR = Path(__file__).parent

# Прокси для OpenAI (Нидерланды)
OPENAI_PROXY_HOST = "77.83.184.128"
OPENAI_PROXY_PORT = "8000"
OPENAI_PROXY_USER = "RVwefb"
OPENAI_PROXY_PASS = "2NVej8"
OPENAI_PROXY_URL = f"http://{OPENAI_PROXY_USER}:{OPENAI_PROXY_PASS}@{OPENAI_PROXY_HOST}:{OPENAI_PROXY_PORT}"


def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
    """Устанавливает SSH соединение."""
    ssh = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Попытка подключения {attempt}/{max_retries}...")
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                hostname, username=username, password=password,
                timeout=timeout, allow_agent=False, look_for_keys=False,
                banner_timeout=30, auth_timeout=30
            )
            
            stdin, stdout, stderr = ssh.exec_command("echo 'test'", timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print("✓ Подключено успешно\n")
                return ssh
        except Exception as e:
            print(f"✗ Ошибка (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                raise
    raise ConnectionError("Не удалось подключиться")


def main():
    print("📋 Копирование .env и настройка прокси для OpenAI")
    print("="*60)
    
    # Ищем .env файл на локальной машине
    local_env = PROJECT_DIR / ".env"
    if not local_env.exists():
        print(f"❌ Файл .env не найден: {local_env}")
        print("Создаю новый .env на сервере с прокси...")
        create_new_env = True
    else:
        print(f"✓ Найден локальный .env: {local_env}")
        create_new_env = False
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        if create_new_env:
            # Создаем новый .env на сервере
            print("\n📝 Создание нового .env на сервере...")
            env_content = f"""# Telegram Bot
BOT_TOKEN=your_bot_token_here

# OpenAI
OPENAI_API_KEY=your_openai_key_here
OPENAI_PROXY={OPENAI_PROXY_URL}

# Admin
ADMIN_IDS=1177786625

# Database
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app

# Redis
REDIS_URL=redis://localhost:6379/0

# YooKassa (на русском сервере прокси не нужен)
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
YOOKASSA_PROXY=
TELEGRAM_PAYMENT_TOKEN=your_payment_token

# API
PUBLIC_BASE_URL=http://93.88.203.86:8000
API_INTERNAL_URL=http://127.0.0.1:8000
WEBHOOK_SECRET=dev-webhook-secret

# Logging
LOG_LEVEL=INFO
"""
            sftp = ssh.open_sftp()
            with sftp.file(f"{SERVER_DIR}/.env", 'w') as f:
                f.write(env_content)
            sftp.close()
            print("✓ Новый .env создан на сервере")
        else:
            # Копируем локальный .env на сервер
            print("\n📤 Копирование .env на сервер...")
            sftp = ssh.open_sftp()
            sftp.put(str(local_env), f"{SERVER_DIR}/.env")
            sftp.close()
            print("✓ .env скопирован на сервер")
        
        # Обновляем OPENAI_PROXY в .env на сервере
        print("\n🔧 Настройка прокси для OpenAI в .env...")
        
        # Читаем текущий .env
        sftp = ssh.open_sftp()
        with sftp.file(f"{SERVER_DIR}/.env", 'r') as f:
            env_content = f.read().decode('utf-8')
        sftp.close()
        
        # Обновляем или добавляем OPENAI_PROXY
        lines = env_content.split('\n')
        updated = False
        new_lines = []
        
        for line in lines:
            if line.startswith('OPENAI_PROXY='):
                new_lines.append(f'OPENAI_PROXY={OPENAI_PROXY_URL}')
                updated = True
            else:
                new_lines.append(line)
        
        if not updated:
            # Добавляем OPENAI_PROXY если его нет
            for i, line in enumerate(new_lines):
                if line.startswith('OPENAI_API_KEY='):
                    new_lines.insert(i + 1, f'OPENAI_PROXY={OPENAI_PROXY_URL}')
                    break
        
        # Убираем YOOKASSA_PROXY (на русском сервере не нужен)
        final_lines = []
        for line in new_lines:
            if line.startswith('YOOKASSA_PROXY='):
                final_lines.append('YOOKASSA_PROXY=')
            else:
                final_lines.append(line)
        
        # Записываем обновленный .env
        sftp = ssh.open_sftp()
        with sftp.file(f"{SERVER_DIR}/.env", 'w') as f:
            f.write('\n'.join(final_lines))
        sftp.close()
        
        print(f"✓ Прокси для OpenAI настроен: http://{OPENAI_PROXY_USER}:****@{OPENAI_PROXY_HOST}:{OPENAI_PROXY_PORT}")
        print("✓ YOOKASSA_PROXY очищен (на русском сервере не нужен)")
        
        # Проверяем наличие базы данных на старом сервере
        print("\n🔍 Проверка базы данных на старом сервере...")
        old_server_ip = "149.33.0.41"
        old_server_user = "root"
        old_server_password = "JuN8AcrM7H"
        
        try:
            old_ssh = connect_ssh(old_server_ip, old_server_user, old_server_password)
            
            # Проверяем, есть ли данные в БД
            check_db_cmd = (
                "sudo -u postgres psql -d app -c "
                "\"SELECT COUNT(*) FROM users;\" 2>/dev/null | tail -n 3 | head -n 1"
            )
            stdin, stdout, stderr = old_ssh.exec_command(check_db_cmd, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            output = stdout.read().decode('utf-8').strip()
            
            if exit_status == 0 and output and output.isdigit():
                user_count = int(output)
                if user_count > 0:
                    print(f"✓ На старом сервере найдено {user_count} пользователей в БД")
                    print("⚠️ Нужно перенести базу данных!")
                    print("\nДля переноса БД выполните:")
                    print(f"1. На старом сервере (149.33.0.41):")
                    print(f"   bash /opt/gptbot/scripts/migrate_to_new_server.sh backup")
                    print(f"2. Скопируйте бэкап на новый сервер:")
                    print(f"   scp /opt/gptbot/backups/migration_backup_*.sql root@93.88.203.86:/opt/gptbot/backups/")
                    print(f"3. На новом сервере (93.88.203.86):")
                    print(f"   bash /opt/gptbot/scripts/migrate_to_new_server.sh restore <имя_файла_бэкапа>")
                else:
                    print("ℹ️ База данных на старом сервере пустая, перенос не требуется")
            else:
                print("⚠️ Не удалось проверить БД на старом сервере")
                print("   Возможно, БД уже перенесена или её нет")
            
            old_ssh.close()
        except Exception as e:
            print(f"⚠️ Не удалось подключиться к старому серверу: {e}")
            print("   Возможно, БД уже перенесена или старая машина недоступна")
        
        print("\n" + "="*60)
        print("✅ НАСТРОЙКА ЗАВЕРШЕНА!")
        print("="*60)
        print("\n📋 Что сделано:")
        print("✓ .env файл скопирован/создан на сервере")
        print(f"✓ Прокси для OpenAI настроен (Нидерланды: {OPENAI_PROXY_HOST}:{OPENAI_PROXY_PORT})")
        print("✓ YOOKASSA_PROXY очищен (на русском сервере не нужен)")
        print("\n⚠️ ВАЖНО: Проверьте .env на сервере и убедитесь, что все токены указаны правильно!")
        print(f"   Файл: /opt/gptbot/.env")
        
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass


if __name__ == "__main__":
    main()

