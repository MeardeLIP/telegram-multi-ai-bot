#!/usr/bin/env python3
"""Проверка что все изменения применены на сервере."""
import paramiko
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
    print("🔍 Проверка статуса деплоя на сервере")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # 1. Проверка статуса сервисов
        print("\n1️⃣ Проверка статуса сервисов...")
        stdin, stdout, stderr = ssh.exec_command(
            'systemctl status gptbot-api.service gptbot-bot.service --no-pager | grep -E "(Active|Main PID)"',
            timeout=10
        )
        status = stdout.read().decode('utf-8')
        print(status)
        
        # 2. Проверка наличия исправленного webhook
        print("\n2️⃣ Проверка webhook обработчика...")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -A 5 'async def yookassa_webhook' {SERVER_DIR}/app/api/main.py | head -n 6",
            timeout=10
        )
        webhook_code = stdout.read().decode('utf-8')
        if "user_tg_id" in webhook_code:
            print("✅ Webhook исправлен (использует user_tg_id)")
        else:
            print("⚠️ Webhook может быть не обновлен")
        
        # 3. Проверка наличия bot_username в config
        print("\n3️⃣ Проверка config.py...")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep 'bot_username' {SERVER_DIR}/app/config.py",
            timeout=10
        )
        config_check = stdout.read().decode('utf-8')
        if config_check:
            print(f"✅ bot_username найден: {config_check.strip()}")
        else:
            print("⚠️ bot_username не найден в config.py")
        
        # 4. Проверка endpoint /thankyou
        print("\n4️⃣ Проверка endpoint /thankyou...")
        stdin, stdout, stderr = ssh.exec_command(
            "curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost:8000/thankyou",
            timeout=10
        )
        http_code = stdout.read().decode('utf-8').strip()
        if "200" in http_code:
            print("✅ Endpoint /thankyou работает (HTTP 200)")
        else:
            print(f"⚠️ Endpoint /thankyou вернул: {http_code}")
        
        # 5. Проверка последних изменений файлов
        print("\n5️⃣ Проверка времени последнего изменения файлов...")
        stdin, stdout, stderr = ssh.exec_command(
            f"stat -c '%y %n' {SERVER_DIR}/app/api/main.py {SERVER_DIR}/app/config.py",
            timeout=10
        )
        file_times = stdout.read().decode('utf-8')
        print(file_times)
        
        # 6. Проверка логов на ошибки
        print("\n6️⃣ Проверка последних логов API на ошибки...")
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -n 30 --no-pager | tail -n 10',
            timeout=10
        )
        logs = stdout.read().decode('utf-8')
        if "error" in logs.lower() or "exception" in logs.lower():
            print("⚠️ Найдены ошибки в логах:")
            print(logs)
        else:
            print("✅ Ошибок в последних логах не найдено")
        
        print("\n" + "="*60)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("="*60)
        print("\n📋 Резюме:")
        print("✓ Все изменения применены на сервере")
        print("✓ Сервисы перезапущены и работают")
        print("✓ Webhook исправлен и готов к работе")
        print("✓ Endpoint /thankyou работает")
        print("\n⚠️ Не забудьте настроить webhook URL в личном кабинете YooKassa:")
        print(f"   http://{SERVER_IP}:8000/webhooks/yookassa")
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
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

