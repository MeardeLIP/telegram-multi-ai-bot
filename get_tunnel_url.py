#!/usr/bin/env python3
"""Получение HTTPS URL от cloudflared туннеля."""
import paramiko
import time
import re

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
    print("🔍 Получение HTTPS URL от cloudflared...")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Ждем немного, чтобы туннель успел запуститься
        print("⏳ Ожидание запуска туннеля...")
        time.sleep(5)
        
        # Получаем логи
        print("\n📋 Проверка логов cloudflared...")
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u cloudflared-tunnel.service -n 50 --no-pager",
            timeout=10
        )
        logs = stdout.read().decode('utf-8')
        
        # Ищем URL в логах
        url_pattern = r'https://[a-z0-9-]+\.trycloudflare\.com'
        urls = re.findall(url_pattern, logs)
        
        if urls:
            tunnel_url = urls[-1]  # Берем последний найденный URL
            webhook_url = f"{tunnel_url}/webhooks/yookassa"
            
            print(f"\n✅ HTTPS URL получен!")
            print(f"\n📋 Используйте этот URL в YooKassa:")
            print(f"   {webhook_url}")
            print(f"\n📋 Или просто домен:")
            print(f"   {tunnel_url}")
            print(f"\n⚠️ ВАЖНО:")
            print(f"   - Этот URL изменится при перезагрузке сервера")
            print(f"   - После перезагрузки запустите этот скрипт снова для получения нового URL")
            print(f"   - Или проверьте логи: journalctl -u cloudflared-tunnel.service -n 30")
        else:
            print("\n⚠️ URL пока не найден в логах")
            print("\n📋 Последние логи:")
            print(logs[-500:] if len(logs) > 500 else logs)
            print("\n💡 Попробуйте подождать еще немного и запустить скрипт снова")
        
        # Проверяем статус
        print("\n📊 Статус сервиса:")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl status cloudflared-tunnel.service --no-pager | head -n 5",
            timeout=10
        )
        status = stdout.read().decode('utf-8')
        print(status)
        
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

