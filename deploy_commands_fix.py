#!/usr/bin/env python3
"""
Деплой исправления команд /myprofile и /refsystem
"""
import paramiko
import time
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"

def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
    """Устанавливает SSH соединение."""
    ssh = None
    for attempt in range(1, max_retries + 1):
        try:
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
                return ssh
        except Exception as e:
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                raise
    raise ConnectionError("Не удалось подключиться")

def main():
    print("🚀 Деплой исправления команд /myprofile и /refsystem")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        sftp = ssh.open_sftp()
        
        # Копируем исправленный файл
        local_file = "app/bot/handlers/start.py"
        remote_file = f"{SERVER_DIR}/app/bot/handlers/start.py"
        
        local_path = Path(local_file)
        if not local_path.exists():
            print(f"   ❌ Локальный файл не найден: {local_file}")
            return
        
        print(f"\n📋 Копирование {local_file}...")
        sftp.put(str(local_path), remote_file)
        print(f"   ✅ Скопирован: {remote_file}")
        
        sftp.close()
        
        # Перезапускаем бота
        print("\n🔄 Перезапуск бота...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl restart gptbot-bot.service",
            timeout=15
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✅ Бот перезапущен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ⚠️ Ошибка перезапуска: {error}")
        
        time.sleep(3)
        
        # Проверяем статус
        print("\n✅ Проверка статуса...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl is-active gptbot-bot.service",
            timeout=10
        )
        status = stdout.read().decode('utf-8').strip()
        print(f"   Статус бота: {status}")
        
        # Проверяем логи на ошибки
        print("\n📋 Проверка логов (последние 5 строк)...")
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service -n 5 --no-pager | tail -5",
            timeout=10
        )
        logs = stdout.read().decode('utf-8')
        if logs.strip():
            print(logs)
        
        print("\n" + "="*60)
        print("✅ ДЕПЛОЙ ЗАВЕРШЕН")
        print("="*60)
        print("\n💡 ИСПРАВЛЕНО:")
        print("   ✅ Команда /myprofile теперь отправляет новое сообщение")
        print("   ✅ Команда /refsystem теперь отправляет новое сообщение")
        print("\n🧪 ТЕСТИРОВАНИЕ:")
        print("   Проверьте команды в боте:")
        print("   - /myprofile - должен показать профиль")
        print("   - /refsystem - должен показать реферальную программу")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
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

