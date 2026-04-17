#!/usr/bin/env python3
"""
Финальная настройка сервера: создание .env и применение миграций.
"""
import paramiko
import socket
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"


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
    print("🔧 Финальная настройка сервера")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Проверяем, существует ли .env
        stdin, stdout, stderr = ssh.exec_command(f"test -f {SERVER_DIR}/.env && echo 'exists' || echo 'not_exists'")
        env_exists = stdout.read().decode('utf-8').strip()
        
        if env_exists == 'exists':
            print("⚠️ Файл .env уже существует. Пропускаем создание.")
        else:
            print("\n📝 Создание шаблона .env файла...")
            env_template = f"""# Telegram Bot
BOT_TOKEN=your_bot_token_here

# OpenAI
OPENAI_API_KEY=your_openai_key_here
OPENAI_PROXY=

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
                f.write(env_template)
            sftp.close()
            print("✓ Шаблон .env создан")
            print("⚠️ ВАЖНО: Отредактируйте /opt/gptbot/.env и укажите реальные значения токенов!")
        
        # Применяем миграции
        print("\n🔄 Применение миграций БД...")
        migrate_cmd = (
            f"cd {SERVER_DIR} && "
            f"source venv/bin/activate && "
            f"python -m alembic upgrade head 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(migrate_cmd, timeout=120)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if exit_status == 0:
            print("✓ Миграции применены успешно")
            if output:
                print(output)
        else:
            print(f"⚠️ Ошибка при применении миграций (код: {exit_status})")
            if error:
                print(f"Ошибка: {error}")
            if output:
                print(f"Вывод: {output}")
        
        print("\n" + "="*60)
        print("✅ ФИНАЛЬНАЯ НАСТРОЙКА ЗАВЕРШЕНА!")
        print("="*60)
        print("\n⚠️ ВАЖНО: Перед запуском сервисов:")
        print("1. Отредактируйте /opt/gptbot/.env и укажите реальные значения:")
        print("   - BOT_TOKEN")
        print("   - OPENAI_API_KEY")
        print("   - YOOKASSA_SHOP_ID")
        print("   - YOOKASSA_SECRET_KEY")
        print("   - TELEGRAM_PAYMENT_TOKEN")
        print("   - OPENAI_PROXY (если нужен прокси для GPT)")
        print("\n2. После настройки .env запустите сервисы:")
        print("   systemctl enable --now gptbot-api.service gptbot-bot.service")
        print("\n3. Проверьте статус:")
        print("   systemctl status gptbot-api.service")
        print("   systemctl status gptbot-bot.service")
        
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

