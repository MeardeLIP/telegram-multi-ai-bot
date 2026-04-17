#!/usr/bin/env python3
"""
Автоматический перенос базы данных со старого сервера на новый.
"""
import paramiko
import socket
import time
from pathlib import Path

OLD_SERVER_IP = "149.33.0.41"
OLD_SERVER_USER = "root"
OLD_SERVER_PASSWORD = "JuN8AcrM7H"
OLD_SERVER_DIR = "/opt/gptbot"

NEW_SERVER_IP = "93.88.203.86"
NEW_SERVER_USER = "root"
NEW_SERVER_PASSWORD = "n5nxGTZeFztJf"
NEW_SERVER_DIR = "/opt/gptbot"

BACKUP_DIR = "/opt/gptbot/backups"


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
    print("🔄 Автоматический перенос базы данных")
    print("="*60)
    
    old_ssh = None
    new_ssh = None
    
    try:
        # Подключаемся к старому серверу
        print("📡 Подключение к старому серверу...")
        old_ssh = connect_ssh(OLD_SERVER_IP, OLD_SERVER_USER, OLD_SERVER_PASSWORD)
        
        # Создаем директорию для бэкапов
        print("\n📁 Создание директории для бэкапов...")
        old_ssh.exec_command(f"mkdir -p {BACKUP_DIR}")
        
        # Создаем бэкап
        print("\n📦 Создание бэкапа базы данных...")
        backup_filename = f"migration_backup_$(date +%Y%m%d_%H%M%S).sql"
        backup_cmd = f"sudo -u postgres pg_dump -d app > {BACKUP_DIR}/{backup_filename}"
        
        stdin, stdout, stderr = old_ssh.exec_command(backup_cmd, timeout=300)
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            error = stderr.read().decode('utf-8')
            print(f"❌ Ошибка при создании бэкапа: {error}")
            raise Exception("Не удалось создать бэкап")
        
        # Получаем имя созданного файла
        list_cmd = f"ls -t {BACKUP_DIR}/migration_backup_*.sql | head -n 1"
        stdin, stdout, stderr = old_ssh.exec_command(list_cmd)
        backup_file = stdout.read().decode('utf-8').strip()
        
        if not backup_file:
            print("❌ Не удалось найти созданный бэкап")
            raise Exception("Бэкап не найден")
        
        backup_filename_only = backup_file.split('/')[-1]
        print(f"✓ Бэкап создан: {backup_filename_only}")
        
        # Получаем размер файла
        size_cmd = f"du -h {backup_file} | cut -f1"
        stdin, stdout, stderr = old_ssh.exec_command(size_cmd)
        backup_size = stdout.read().decode('utf-8').strip()
        print(f"  Размер: {backup_size}")
        
        # Копируем бэкап на новый сервер
        print("\n📤 Копирование бэкапа на новый сервер...")
        new_ssh = connect_ssh(NEW_SERVER_IP, NEW_SERVER_USER, NEW_SERVER_PASSWORD)
        new_ssh.exec_command(f"mkdir -p {BACKUP_DIR}")
        
        # Используем scp через SSH
        sftp_old = old_ssh.open_sftp()
        sftp_new = new_ssh.open_sftp()
        
        print(f"  Копирование {backup_filename_only}...")
        remote_file_old = sftp_old.open(backup_file, 'rb')
        remote_file_new = sftp_new.file(f"{BACKUP_DIR}/{backup_filename_only}", 'wb')
        
        # Копируем файл по частям
        chunk_size = 8192
        total_size = 0
        while True:
            chunk = remote_file_old.read(chunk_size)
            if not chunk:
                break
            remote_file_new.write(chunk)
            total_size += len(chunk)
            if total_size % (1024 * 1024) == 0:  # Показываем прогресс каждые MB
                print(f"  Скопировано: {total_size / (1024 * 1024):.1f} MB", end='\r')
        
        remote_file_old.close()
        remote_file_new.close()
        sftp_old.close()
        sftp_new.close()
        
        print(f"\n✓ Бэкап скопирован на новый сервер ({total_size / (1024 * 1024):.1f} MB)")
        
        # Останавливаем сервисы на новом сервере
        print("\n⏸️ Остановка сервисов на новом сервере...")
        new_ssh.exec_command("systemctl stop gptbot-api.service gptbot-bot.service 2>/dev/null || true")
        time.sleep(2)
        
        # Восстанавливаем БД
        print("\n📥 Восстановление базы данных...")
        restore_cmd = f"sudo -u postgres psql -d app < {BACKUP_DIR}/{backup_filename_only}"
        stdin, stdout, stderr = new_ssh.exec_command(restore_cmd, timeout=300)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if exit_status != 0:
            print(f"⚠️ Ошибка при восстановлении (код: {exit_status})")
            if error:
                print(f"Ошибка: {error[-500:]}")
            if output:
                print(f"Вывод: {output[-500:]}")
        else:
            print("✓ База данных восстановлена")
        
        # Применяем миграции (на случай если структура изменилась)
        print("\n🔄 Применение миграций...")
        migrate_cmd = (
            f"cd {NEW_SERVER_DIR} && "
            f"source venv/bin/activate && "
            f"python -m alembic upgrade head 2>&1"
        )
        stdin, stdout, stderr = new_ssh.exec_command(migrate_cmd, timeout=120)
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        
        if exit_status == 0:
            print("✓ Миграции применены")
        else:
            print(f"⚠️ Ошибка при применении миграций (код: {exit_status})")
            if output:
                print(f"Вывод: {output[-500:]}")
        
        # Запускаем сервисы
        print("\n▶️ Запуск сервисов...")
        new_ssh.exec_command("systemctl start gptbot-api.service gptbot-bot.service")
        time.sleep(2)
        
        # Проверяем статус
        print("\n📊 Проверка статуса сервисов...")
        stdin, stdout, stderr = new_ssh.exec_command("systemctl status gptbot-api.service --no-pager -l | head -n 10")
        api_status = stdout.read().decode('utf-8')
        print("API сервис:")
        print(api_status)
        
        stdin, stdout, stderr = new_ssh.exec_command("systemctl status gptbot-bot.service --no-pager -l | head -n 10")
        bot_status = stdout.read().decode('utf-8')
        print("\nBot сервис:")
        print(bot_status)
        
        print("\n" + "="*60)
        print("✅ ПЕРЕНОС БАЗЫ ДАННЫХ ЗАВЕРШЕН!")
        print("="*60)
        print("\n📋 Что сделано:")
        print("✓ Бэкап БД создан на старом сервере")
        print("✓ Бэкап скопирован на новый сервер")
        print("✓ База данных восстановлена")
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
        if old_ssh:
            try:
                old_ssh.close()
            except:
                pass
        if new_ssh:
            try:
                new_ssh.close()
            except:
                pass


if __name__ == "__main__":
    main()

