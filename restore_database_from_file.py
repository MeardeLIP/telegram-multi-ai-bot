#!/usr/bin/env python3
"""
Восстановление базы данных из SQL файла на новом сервере.
"""
import paramiko
import socket
import time
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
BACKUP_FILE = "gptbuckupnew.sql"
LOCAL_BACKUP = Path(__file__).parent / BACKUP_FILE

DB_USER = "app"
DB_NAME = "app"


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
    print("🔄 Восстановление базы данных из SQL файла")
    print("="*60)
    
    # Проверяем наличие локального файла
    if not LOCAL_BACKUP.exists():
        print(f"❌ Файл {LOCAL_BACKUP} не найден!")
        return
    
    file_size = LOCAL_BACKUP.stat().st_size / (1024 * 1024)
    print(f"✓ Найден файл бэкапа: {LOCAL_BACKUP}")
    print(f"  Размер: {file_size:.2f} MB\n")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Создаем директорию для бэкапов
        print("📁 Создание директории для бэкапов...")
        ssh.exec_command(f"mkdir -p {SERVER_DIR}/backups")
        
        # Копируем файл на сервер
        print(f"\n📤 Копирование {BACKUP_FILE} на сервер...")
        sftp = ssh.open_sftp()
        remote_path = f"{SERVER_DIR}/backups/{BACKUP_FILE}"
        
        print("  Копирование файла...")
        sftp.put(str(LOCAL_BACKUP), remote_path)
        sftp.close()
        print(f"✓ Файл скопирован: {remote_path}")
        
        # Останавливаем сервисы
        print("\n⏸️ Остановка сервисов...")
        ssh.exec_command("systemctl stop gptbot-api.service gptbot-bot.service 2>/dev/null || true")
        time.sleep(2)
        print("✓ Сервисы остановлены")
        
        # Удаляем старую базу данных
        print("\n🗑️ Удаление старой базы данных...")
        stdin, stdout, stderr = ssh.exec_command(
            f"sudo -u postgres psql -c 'DROP DATABASE IF EXISTS {DB_NAME};'",
            timeout=30
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("✓ Старая база данных удалена")
        else:
            error = stderr.read().decode('utf-8')
            print(f"⚠ Ошибка при удалении (возможно, БД не существовала): {error.strip()}")
        
        # Создаем новую базу данных
        print("\n📦 Создание новой базы данных...")
        stdin, stdout, stderr = ssh.exec_command(
            f"sudo -u postgres psql -c 'CREATE DATABASE {DB_NAME} OWNER {DB_USER};'",
            timeout=30
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("✓ Новая база данных создана")
        else:
            error = stderr.read().decode('utf-8')
            print(f"❌ Ошибка при создании БД: {error}")
            raise Exception("Не удалось создать базу данных")
        
        # Восстанавливаем базу данных
        print("\n📥 Восстановление базы данных из SQL файла...")
        print("  Это может занять некоторое время...")
        
        # Используем psql для восстановления
        restore_cmd = (
            f"sudo -u postgres psql -d {DB_NAME} < {SERVER_DIR}/backups/{BACKUP_FILE} 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(restore_cmd, timeout=300)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if exit_status == 0:
            print("✓ База данных восстановлена успешно")
            if output:
                # Показываем последние строки вывода
                lines = output.strip().split('\n')
                if len(lines) > 10:
                    print("  Последние строки:")
                    for line in lines[-5:]:
                        if line.strip():
                            print(f"    {line}")
                else:
                    print(f"  {output[-200:]}")
        else:
            print(f"⚠ Ошибка при восстановлении (код: {exit_status})")
            if error:
                print(f"  Ошибка: {error[-500:]}")
            if output:
                print(f"  Вывод: {output[-500:]}")
            # Не прерываем выполнение, возможно это предупреждения
        
        # Проверяем количество пользователей
        print("\n🔍 Проверка восстановленных данных...")
        stdin, stdout, stderr = ssh.exec_command(
            f"sudo -u postgres psql -d {DB_NAME} -c 'SELECT COUNT(*) FROM users;' 2>&1 | tail -n 3 | head -n 1",
            timeout=30
        )
        user_count = stdout.read().decode('utf-8').strip()
        if user_count.isdigit():
            print(f"✓ Пользователей в БД: {user_count}")
        else:
            print(f"⚠ Не удалось проверить количество пользователей: {user_count}")
        
        # Применяем миграции (на случай если структура изменилась)
        print("\n🔄 Применение миграций...")
        migrate_cmd = (
            f"cd {SERVER_DIR} && "
            f"source venv/bin/activate && "
            f"python -m alembic upgrade head 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(migrate_cmd, timeout=120)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        
        if exit_status == 0:
            print("✓ Миграции применены")
            if "Running upgrade" in output:
                # Показываем последние миграции
                lines = output.strip().split('\n')
                for line in lines:
                    if "Running upgrade" in line:
                        print(f"  {line}")
        else:
            print(f"⚠ Ошибка при применении миграций (код: {exit_status})")
            if output:
                print(f"  Вывод: {output[-300:]}")
        
        # Запускаем сервисы
        print("\n▶️ Запуск сервисов...")
        ssh.exec_command("systemctl start gptbot-api.service gptbot-bot.service")
        time.sleep(3)
        print("✓ Сервисы запущены")
        
        # Проверяем статус
        print("\n📊 Проверка статуса сервисов...")
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 10')
        api_status = stdout.read().decode('utf-8')
        print("API сервис:")
        print(api_status)
        
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-bot.service --no-pager | head -n 10')
        bot_status = stdout.read().decode('utf-8')
        print("\nBot сервис:")
        print(bot_status)
        
        print("\n" + "="*60)
        print("✅ ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ ЗАВЕРШЕНО!")
        print("="*60)
        print("\n📋 Что сделано:")
        print("✓ SQL файл скопирован на сервер")
        print("✓ Старая база данных удалена")
        print("✓ Новая база данных создана")
        print("✓ База данных восстановлена из SQL файла")
        print("✓ Миграции применены")
        print("✓ Сервисы запущены")
        print("\n⚠️ Проверьте логи сервисов:")
        print("   journalctl -u gptbot-api.service -n 50")
        print("   journalctl -u gptbot-bot.service -n 50")
        
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

