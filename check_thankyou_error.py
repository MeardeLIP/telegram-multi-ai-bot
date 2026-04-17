#!/usr/bin/env python3
"""Проверка ошибки в endpoint /thankyou."""
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
        
        print("🔍 Проверка ошибки в endpoint /thankyou...")
        print("="*60)
        
        # Проверяем последние логи API
        print("\n📋 Последние логи API сервиса (последние 30 строк)...")
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -n 30 --no-pager',
            timeout=10
        )
        logs = stdout.read().decode('utf-8')
        print(logs)
        
        # Пробуем сделать запрос и посмотреть ошибку
        print("\n📋 Попытка запроса к /thankyou...")
        stdin, stdout, stderr = ssh.exec_command(
            "curl -v http://localhost:8000/thankyou 2>&1 | tail -n 20",
            timeout=10
        )
        curl_output = stdout.read().decode('utf-8')
        print(curl_output)
        
        # Проверяем, что файл main.py содержит endpoint
        print("\n📋 Проверка наличия endpoint /thankyou в коде...")
        stdin, stdout, stderr = ssh.exec_command(
            "grep -n 'def thankyou_page' /opt/gptbot/app/api/main.py || echo 'NOT FOUND'",
            timeout=10
        )
        grep_result = stdout.read().decode('utf-8')
        print(grep_result)
        
        # Проверяем импорты
        print("\n📋 Проверка импортов HTMLResponse...")
        stdin, stdout, stderr = ssh.exec_command(
            "grep -n 'HTMLResponse' /opt/gptbot/app/api/main.py | head -n 5",
            timeout=10
        )
        imports = stdout.read().decode('utf-8')
        print(imports)
        
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

