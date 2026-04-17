#!/usr/bin/env python3
"""Скрипт для деплоя app/services/image_generation.py на сервер."""
import paramiko
import os
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_DIR = "/opt/gptbot"
FILE_TO_DEPLOY = "app/services/image_generation.py"
PROJECT_DIR = Path(__file__).parent


def get_password() -> str:
    """Возвращает пароль для подключения к серверу."""
    env_password = os.getenv("GPTBOT_SERVER_PASSWORD")
    if env_password:
        return env_password
    return input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")


def main() -> None:
    password = get_password()
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"🔌 Подключение к {SERVER_USER}@{SERVER_IP}...")
        ssh.connect(SERVER_IP, username=SERVER_USER, password=password, timeout=10)
        print("✓ Подключено к серверу\n")
        
        # Открываем SFTP для копирования файла
        sftp = ssh.open_sftp()
        
        local_path = PROJECT_DIR / FILE_TO_DEPLOY
        if not local_path.exists():
            print(f"❌ Файл не найден локально: {local_path}")
            return
        
        remote_path = f"{SERVER_DIR}/{FILE_TO_DEPLOY}"
        remote_dir = os.path.dirname(remote_path)
        
        # Создаем директорию на сервере, если её нет
        print(f"📁 Создание директории {remote_dir}...")
        ssh.exec_command(f"mkdir -p {remote_dir}")
        
        # Копируем файл
        print(f"📤 Копирование {FILE_TO_DEPLOY} на сервер...")
        sftp.put(str(local_path), remote_path)
        sftp.close()
        print(f"✓ Файл скопирован: {remote_path}\n")
        
        # Проверяем, что файл скопирован корректно
        print("🔍 Проверка файла на сервере...")
        stdin, stdout, stderr = ssh.exec_command(f"test -f {remote_path} && echo 'exists' || echo 'not_found'")
        result = stdout.read().decode('utf-8').strip()
        if result == "exists":
            print("✓ Файл найден на сервере")
            
            # Проверяем наличие функции create_edit_prompt
            stdin, stdout, stderr = ssh.exec_command(f"grep -q 'def create_edit_prompt' {remote_path} && echo 'found' || echo 'not_found'")
            func_check = stdout.read().decode('utf-8').strip()
            if func_check == "found":
                print("✓ Функция create_edit_prompt найдена в файле")
            else:
                print("⚠ Функция create_edit_prompt не найдена в файле!")
        else:
            print("❌ Файл не найден на сервере!")
            return
        
        # Перезапускаем сервис
        print("\n🔄 Перезапуск сервиса gptbot-bot.service...")
        stdin, stdout, stderr = ssh.exec_command("systemctl restart gptbot-bot.service")
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status == 0:
            print("✓ Сервис перезапущен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"⚠ Ошибка при перезапуске сервиса: {error}")
        
        # Проверяем статус сервиса
        print("\n📊 Проверка статуса сервиса...")
        stdin, stdout, stderr = ssh.exec_command("systemctl status gptbot-bot.service --no-pager -l -n 10")
        status_output = stdout.read().decode('utf-8')
        print(status_output)
        
        if "Active: active (running)" in status_output:
            print("\n✅ Сервис успешно запущен!")
        elif "Active: activating" in status_output:
            print("\n⏳ Сервис запускается...")
        else:
            print("\n⚠ Сервис может быть не запущен. Проверьте логи.")
        
        print("\n✅ Деплой завершен!")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
