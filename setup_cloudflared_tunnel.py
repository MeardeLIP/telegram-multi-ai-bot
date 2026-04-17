#!/usr/bin/env python3
"""
Настройка cloudflared туннеля для получения HTTPS URL для webhook.
"""
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
    print("🌐 Настройка cloudflared туннеля для HTTPS")
    print("="*60)
    print("\n📋 Cloudflared создаст бесплатный HTTPS туннель к вашему серверу")
    print("   Это даст вам URL вида: https://xxxxx.trycloudflare.com/webhooks/yookassa")
    print("\n⚠️ ВАЖНО: URL будет меняться при каждом перезапуске туннеля!")
    print("   Для постоянного URL лучше настроить SSL на сервере (Вариант 2)")
    
    print("\n" + "="*60)
    print("ВАРИАНТ 1: Cloudflared туннель (быстро, но URL меняется)")
    print("="*60)
    print("\n1. Установите cloudflared на сервере:")
    print("   wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64")
    print("   chmod +x cloudflared-linux-amd64")
    print("   mv cloudflared-linux-amd64 /usr/local/bin/cloudflared")
    print("\n2. Запустите туннель:")
    print("   cloudflared tunnel --url http://localhost:8000")
    print("\n3. Скопируйте полученный HTTPS URL (например: https://xxxxx.trycloudflare.com)")
    print("4. Используйте этот URL в YooKassa: https://xxxxx.trycloudflare.com/webhooks/yookassa")
    
    print("\n" + "="*60)
    print("ВАРИАНТ 2: SSL сертификат через Let's Encrypt (постоянный URL)")
    print("="*60)
    print("\n📋 Для этого нужен домен, указывающий на ваш сервер")
    print("   Если домена нет, используйте Вариант 1")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        print("\n🔍 Проверка наличия cloudflared на сервере...")
        stdin, stdout, stderr = ssh.exec_command("which cloudflared || echo 'not found'")
        cloudflared_path = stdout.read().decode('utf-8').strip()
        
        if "not found" in cloudflared_path:
            print("❌ cloudflared не установлен")
            print("\n📥 Установить cloudflared? (y/n): ", end="")
            install = input().strip().lower()
            
            if install == 'y':
                print("\n📥 Установка cloudflared...")
                commands = [
                    "wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /tmp/cloudflared",
                    "chmod +x /tmp/cloudflared",
                    "mv /tmp/cloudflared /usr/local/bin/cloudflared",
                    "cloudflared --version"
                ]
                
                for cmd in commands:
                    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
                    exit_status = stdout.channel.recv_exit_status()
                    if exit_status == 0:
                        output = stdout.read().decode('utf-8')
                        print(f"✓ {cmd}")
                        if "cloudflared version" in output or "version" in output.lower():
                            print(f"  {output.strip()}")
                    else:
                        error = stderr.read().decode('utf-8')
                        print(f"✗ Ошибка: {error}")
                
                print("\n✅ Cloudflared установлен!")
                print("\n📋 Теперь запустите туннель в отдельном терминале:")
                print("   cloudflared tunnel --url http://localhost:8000")
                print("\n📋 Или создайте systemd сервис для автозапуска:")
                print("   (я могу помочь с этим)")
        else:
            print(f"✅ cloudflared уже установлен: {cloudflared_path}")
            print("\n📋 Запустите туннель командой:")
            print("   cloudflared tunnel --url http://localhost:8000")
        
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

