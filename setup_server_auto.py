#!/usr/bin/env python3
"""
Автоматическая настройка нового сервера.
Выполняет все необходимые шаги для переноса проекта.
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


def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
    """Устанавливает SSH соединение с повторными попытками."""
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
                hostname,
                username=username,
                password=password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
                banner_timeout=30,
                auth_timeout=30
            )
            
            stdin, stdout, stderr = ssh.exec_command("echo 'test'", timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                print("✓ Подключено успешно\n")
                return ssh
            else:
                raise paramiko.SSHException(f"Тестовая команда вернула код {exit_status}")
                
        except Exception as e:
            print(f"✗ Ошибка (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = 2 * attempt
                print(f"  → Ожидание {wait_time} секунд...")
                time.sleep(wait_time)
            else:
                raise
    
    raise ConnectionError("Не удалось подключиться после всех попыток")


def execute_command(ssh, command, description, check_output=False):
    """Выполняет команду на сервере и выводит результат."""
    print(f"\n{description}...")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=300)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')
    
    if exit_status == 0:
        if output.strip():
            print(output.strip())
        print(f"✓ {description} - успешно")
        return True, output
    else:
        print(f"✗ {description} - ошибка (код: {exit_status})")
        if error:
            print(f"Ошибка: {error}")
        if output:
            print(f"Вывод: {output}")
        return False, output


def main():
    print("🚀 Автоматическая настройка нового сервера")
    print(f"Сервер: {SERVER_USER}@{SERVER_IP}\n")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Шаг 1: Обновление системы и установка зависимостей
        print("\n" + "="*60)
        print("ШАГ 1: Установка системных зависимостей")
        print("="*60)
        
        execute_command(ssh, "apt-get update -y", "Обновление списка пакетов")
        execute_command(ssh, 
            "apt-get install -y python3.11 python3.11-venv python3.11-dev postgresql postgresql-contrib redis-server git curl wget build-essential libpq-dev libssl-dev libffi-dev",
            "Установка системных зависимостей")
        
        # Шаг 2: Создание пользователя и директории
        print("\n" + "="*60)
        print("ШАГ 2: Создание пользователя и директории")
        print("="*60)
        
        execute_command(ssh, 
            "id gptbot 2>/dev/null || useradd -m -s /bin/bash gptbot",
            "Создание пользователя gptbot")
        execute_command(ssh, "mkdir -p /opt/gptbot", "Создание директории проекта")
        execute_command(ssh, "chown gptbot:gptbot /opt/gptbot", "Настройка прав доступа")
        
        # Шаг 3: Настройка PostgreSQL
        print("\n" + "="*60)
        print("ШАГ 3: Настройка PostgreSQL")
        print("="*60)
        
        execute_command(ssh,
            "sudo -u postgres psql -c \"CREATE USER app WITH PASSWORD 'app';\" 2>/dev/null || true",
            "Создание пользователя БД")
        execute_command(ssh,
            "sudo -u postgres psql -c \"CREATE DATABASE app OWNER app;\" 2>/dev/null || true",
            "Создание базы данных")
        execute_command(ssh,
            "sudo -u postgres psql -c \"GRANT ALL PRIVILEGES ON DATABASE app TO app;\"",
            "Настройка прав доступа к БД")
        
        # Шаг 4: Настройка Redis
        print("\n" + "="*60)
        print("ШАГ 4: Настройка Redis")
        print("="*60)
        
        execute_command(ssh, "systemctl enable redis-server", "Включение автозапуска Redis")
        execute_command(ssh, "systemctl start redis-server", "Запуск Redis")
        
        # Шаг 5: Создание виртуального окружения
        print("\n" + "="*60)
        print("ШАГ 5: Создание виртуального окружения Python")
        print("="*60)
        
        execute_command(ssh,
            "[ -d /opt/gptbot/venv ] || sudo -u gptbot python3.11 -m venv /opt/gptbot/venv",
            "Создание виртуального окружения")
        
        # Шаг 6: Копирование файлов проекта
        print("\n" + "="*60)
        print("ШАГ 6: Копирование файлов проекта")
        print("="*60)
        
        print("Копирование файлов через SFTP...")
        sftp = ssh.open_sftp()
        
        # Список файлов и директорий для копирования
        files_to_copy = [
            "app",
            "alembic.ini",
            "requirements.txt",
            "scripts",
            "photo_2025-12-03_02-41-09.jpg",
        ]
        
        def copy_file_or_dir(local_path, remote_path):
            """Рекурсивно копирует файл или директорию."""
            local = PROJECT_DIR / local_path
            if not local.exists():
                print(f"⚠ Пропущен (не найден): {local_path}")
                return
            
            if local.is_file():
                remote_dir = os.path.dirname(remote_path)
                ssh.exec_command(f"mkdir -p {remote_dir}")
                sftp.put(str(local), remote_path)
                print(f"✓ {local_path}")
            elif local.is_dir():
                ssh.exec_command(f"mkdir -p {remote_path}")
                for item in local.rglob("*"):
                    if item.is_file():
                        rel_path = item.relative_to(local)
                        remote_file = f"{remote_path}/{rel_path}".replace("\\", "/")
                        remote_dir = os.path.dirname(remote_file)
                        ssh.exec_command(f"mkdir -p {remote_dir}")
                        sftp.put(str(item), remote_file)
                print(f"✓ {local_path}/ (директория)")
        
        for item in files_to_copy:
            copy_file_or_dir(item, f"{SERVER_DIR}/{item}")
        
        sftp.close()
        
        # Установка прав на скрипты
        execute_command(ssh, "chmod +x /opt/gptbot/scripts/*.sh", "Установка прав на скрипты")
        execute_command(ssh, "chown -R gptbot:gptbot /opt/gptbot", "Установка владельца файлов")
        
        # Шаг 7: Установка Python зависимостей
        print("\n" + "="*60)
        print("ШАГ 7: Установка Python зависимостей")
        print("="*60)
        
        execute_command(ssh,
            f"cd {SERVER_DIR} && sudo -u gptbot {SERVER_DIR}/venv/bin/pip install --upgrade pip",
            "Обновление pip")
        execute_command(ssh,
            f"cd {SERVER_DIR} && sudo -u gptbot {SERVER_DIR}/venv/bin/pip install -r requirements.txt",
            "Установка зависимостей из requirements.txt")
        
        # Шаг 8: Копирование systemd сервисов
        print("\n" + "="*60)
        print("ШАГ 8: Настройка systemd сервисов")
        print("="*60)
        
        # Копируем файлы сервисов
        for service_file in ["gptbot-api.service", "gptbot-bot.service"]:
            local_service = PROJECT_DIR / "scripts" / service_file
            if local_service.exists():
                sftp = ssh.open_sftp()
                sftp.put(str(local_service), f"/etc/systemd/system/{service_file}")
                sftp.close()
                print(f"✓ Скопирован {service_file}")
        
        execute_command(ssh, "systemctl daemon-reload", "Перезагрузка systemd")
        
        print("\n" + "="*60)
        print("✅ НАСТРОЙКА СЕРВЕРА ЗАВЕРШЕНА!")
        print("="*60)
        print("\nСледующие шаги:")
        print("1. Создайте файл .env в /opt/gptbot/.env с настройками:")
        print("   - BOT_TOKEN")
        print("   - OPENAI_API_KEY")
        print("   - ADMIN_IDS")
        print("   - YOOKASSA_SHOP_ID")
        print("   - YOOKASSA_SECRET_KEY")
        print("   - TELEGRAM_PAYMENT_TOKEN")
        print("   - PUBLIC_BASE_URL=http://93.88.203.86:8000")
        print("   - OPENAI_PROXY (если нужен прокси для GPT)")
        print("   - DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app")
        print("   - REDIS_URL=redis://localhost:6379/0")
        print("\n2. Примените миграции БД:")
        print(f"   cd {SERVER_DIR} && source venv/bin/activate && python -m alembic upgrade head")
        print("\n3. Включите и запустите сервисы:")
        print("   systemctl enable --now gptbot-api.service gptbot-bot.service")
        print("\n4. Проверьте статус:")
        print("   systemctl status gptbot-api.service")
        print("   systemctl status gptbot-bot.service")
        
    except KeyboardInterrupt:
        print("\n✗ Прервано пользователем")
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

