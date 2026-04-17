#!/usr/bin/env python3
"""Обновление app/api/main.py на сервере."""
import paramiko
import time
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
LOCAL_FILE = Path(__file__).parent / "app" / "api" / "main.py"
REMOTE_FILE = f"{SERVER_DIR}/app/api/main.py"


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
    print("🔄 Обновление app/api/main.py на сервере")
    print("="*60)
    
    if not LOCAL_FILE.exists():
        print(f"❌ Локальный файл не найден: {LOCAL_FILE}")
        return
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Копируем файл
        print(f"📤 Копирование {LOCAL_FILE.name} на сервер...")
        sftp = ssh.open_sftp()
        
        # Создаем директорию если нужно
        ssh.exec_command(f"mkdir -p {SERVER_DIR}/app/api")
        
        # Копируем файл
        sftp.put(str(LOCAL_FILE), REMOTE_FILE)
        sftp.close()
        print(f"✓ Файл скопирован: {REMOTE_FILE}")
        
        # Проверяем, что webhook обработчик есть в файле
        print("\n🔍 Проверка наличия webhook обработчика...")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -n 'async def yookassa_webhook' {REMOTE_FILE}",
            timeout=10
        )
        grep_result = stdout.read().decode('utf-8')
        if grep_result:
            print("✓ Webhook обработчик найден:")
            print(f"  {grep_result.strip()}")
        else:
            print("⚠️ Webhook обработчик не найден!")
        
        # Перезапускаем API сервис
        print("\n🔄 Перезапуск API сервиса...")
        ssh.exec_command("systemctl restart gptbot-api.service")
        time.sleep(3)
        print("✓ API сервис перезапущен")
        
        # Проверяем статус
        print("\n📊 Проверка статуса API сервиса...")
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 10')
        status = stdout.read().decode('utf-8')
        print(status)
        
        # Проверяем логи на ошибки
        print("\n🔍 Проверка последних логов на ошибки...")
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -n 20 --no-pager | grep -i "error\|exception\|traceback" || echo "Ошибок не найдено"',
            timeout=10
        )
        errors = stdout.read().decode('utf-8')
        if errors and "Ошибок не найдено" not in errors:
            print("⚠️ Найдены ошибки в логах:")
            print(errors)
        else:
            print("✓ Ошибок в логах не найдено")
        
        print("\n" + "="*60)
        print("✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!")
        print("="*60)
        print("\n📋 Что исправлено:")
        print("✓ Webhook теперь ищет пользователя по Telegram ID (не внутреннему ID)")
        print("✓ Добавлено детальное логирование webhook")
        print("✓ Обновляется статус платежа в БД")
        print("✓ Отправляется уведомление пользователю в бот после успешной оплаты")
        
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

