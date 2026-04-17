#!/usr/bin/env python3
"""Исправление прав доступа к .env файлу."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
ENV_FILE = f"{SERVER_DIR}/.env"


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
        
        # Проверяем текущие права
        print("📋 Проверка текущих прав доступа...")
        stdin, stdout, stderr = ssh.exec_command(f"ls -la {ENV_FILE}", timeout=10)
        current_perms = stdout.read().decode('utf-8')
        print(current_perms)
        
        # Исправляем права доступа (читаемый для всех, но только владелец может писать)
        print("\n🔧 Исправление прав доступа...")
        stdin, stdout, stderr = ssh.exec_command(
            f"chmod 644 {ENV_FILE} && chown gptbot:gptbot {ENV_FILE}",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("✓ Права доступа исправлены")
        else:
            error = stderr.read().decode('utf-8')
            print(f"⚠ Ошибка: {error}")
        
        # Проверяем новые права
        print("\n📋 Проверка новых прав доступа...")
        stdin, stdout, stderr = ssh.exec_command(f"ls -la {ENV_FILE}", timeout=10)
        new_perms = stdout.read().decode('utf-8')
        print(new_perms)
        
        # Запускаем API сервис
        print("\n▶️ Запуск API сервиса...")
        stdin, stdout, stderr = ssh.exec_command("systemctl start gptbot-api.service", timeout=10)
        time.sleep(3)
        
        # Проверяем статус
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 15')
        status = stdout.read().decode('utf-8')
        print(status)
        
        if "active (running)" in status:
            print("\n✅ API сервис успешно запущен!")
        else:
            print("\n⚠️ API сервис не запустился, проверьте логи:")
            print("   journalctl -u gptbot-api.service -n 20")
        
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

