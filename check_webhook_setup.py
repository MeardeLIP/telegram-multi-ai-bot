#!/usr/bin/env python3
"""Проверка настройки webhook для YooKassa."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"

WEBHOOK_URL = f"http://{SERVER_IP}:8000/webhooks/yookassa"


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
    print("🔍 Проверка настройки webhook для YooKassa")
    print("="*60)
    
    print(f"\n📋 Webhook URL должен быть настроен в личном кабинете YooKassa:")
    print(f"   {WEBHOOK_URL}")
    
    print(f"\n📋 Проверка доступности webhook endpoint...")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Проверяем доступность endpoint
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTP Status: %{{http_code}}\n' -X POST http://localhost:8000/webhooks/yookassa -H 'Content-Type: application/json' -d '{{}}'",
            timeout=10
        )
        http_code = stdout.read().decode('utf-8').strip()
        print(f"   HTTP Status: {http_code}")
        
        if "400" in http_code or "200" in http_code:
            print("   ✅ Endpoint доступен (400 или 200 - это нормально для пустого запроса)")
        else:
            print(f"   ⚠️ Неожиданный статус: {http_code}")
        
        # Проверяем последние логи webhook
        print(f"\n📋 Последние логи webhook (последние 10 строк)...")
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -n 50 --no-pager | grep -i "webhook\|yookassa" | tail -n 10 || echo "Логов webhook не найдено"',
            timeout=10
        )
        logs = stdout.read().decode('utf-8')
        if logs and "Логов webhook не найдено" not in logs:
            print(logs)
        else:
            print("   Логов webhook пока нет (это нормально, если платежей не было)")
        
        print("\n" + "="*60)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("="*60)
        print("\n📋 Инструкция по настройке webhook в YooKassa:")
        print("1. Войдите в личный кабинет YooKassa")
        print("2. Перейдите в раздел 'Настройки' → 'Уведомления'")
        print(f"3. Укажите URL для уведомлений: {WEBHOOK_URL}")
        print("4. Сохраните настройки")
        print("\n⚠️ Важно: YooKassa будет отправлять уведомления на этот URL")
        print("   при изменении статуса платежа (pending → succeeded)")
        
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

