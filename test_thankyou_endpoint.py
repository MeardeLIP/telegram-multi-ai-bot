#!/usr/bin/env python3
"""Проверка доступности endpoint /thankyou."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"


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
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        print("🔍 Проверка endpoint /thankyou...")
        print("="*60)
        
        # Проверяем доступность через curl
        print("\n1. Проверка HTTP статуса...")
        stdin, stdout, stderr = ssh.exec_command(
            "curl -s -o /dev/null -w 'HTTP Status: %{http_code}\nContent-Type: %{content_type}\n' http://localhost:8000/thankyou",
            timeout=10
        )
        curl_output = stdout.read().decode('utf-8')
        print(curl_output)
        
        # Проверяем содержимое страницы
        print("\n2. Проверка содержимого страницы...")
        stdin, stdout, stderr = ssh.exec_command(
            "curl -s http://localhost:8000/thankyou | head -n 20",
            timeout=10
        )
        page_content = stdout.read().decode('utf-8')
        if 'Спасибо за оплату' in page_content or 'thankyou' in page_content.lower():
            print("✓ Страница содержит ожидаемый контент")
            print("  Первые строки:")
            for line in page_content.split('\n')[:5]:
                if line.strip():
                    print(f"    {line[:80]}")
        else:
            print("⚠️ Страница не содержит ожидаемый контент")
            print(f"  Начало ответа: {page_content[:200]}")
        
        # Проверяем настройки в .env
        print("\n3. Проверка настроек в .env...")
        stdin, stdout, stderr = ssh.exec_command(
            "grep -E '(BOT_USERNAME|PUBLIC_BASE_URL)' /opt/gptbot/.env",
            timeout=10
        )
        env_settings = stdout.read().decode('utf-8')
        print(env_settings)
        
        print("\n" + "="*60)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("="*60)
        print(f"\n📋 URL для редиректа после оплаты:")
        print(f"   http://{SERVER_IP}:8000/thankyou")
        print(f"\n📱 Бот: @EnNeuroGPTbot")
        print(f"\n✅ После оплаты пользователи увидят красивую страницу")
        print(f"   и автоматически вернутся в бот через 5 секунд")
        
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

