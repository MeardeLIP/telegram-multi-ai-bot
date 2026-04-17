#!/usr/bin/env python3
"""Проверка и запуск API сервиса."""
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
        
        # Проверяем логи API сервиса
        print("📋 Проверка логов API сервиса...")
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -n 30 --no-pager',
            timeout=30
        )
        logs = stdout.read().decode('utf-8')
        print(logs)
        
        # Запускаем API сервис
        print("\n▶️ Запуск API сервиса...")
        stdin, stdout, stderr = ssh.exec_command("systemctl start gptbot-api.service", timeout=10)
        time.sleep(3)
        
        # Проверяем статус
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 15')
        status = stdout.read().decode('utf-8')
        print(status)
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass


if __name__ == "__main__":
    main()

