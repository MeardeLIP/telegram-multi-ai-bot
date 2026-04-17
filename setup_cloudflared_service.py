#!/usr/bin/env python3
"""
Настройка cloudflared как systemd сервиса для постоянной работы.
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
    print("🔧 Настройка cloudflared как systemd сервиса")
    print("="*60)
    print("\n⚠️ ВАЖНО:")
    print("   - Cloudflared будет работать постоянно")
    print("   - НО URL будет меняться при перезапуске сервера")
    print("   - Для постоянного URL нужен именованный туннель (требует регистрации)")
    print("\n✅ Преимущества:")
    print("   - Автозапуск при перезагрузке сервера")
    print("   - Автоматический перезапуск при сбое")
    print("   - Бесплатный HTTPS")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # 1. Установка cloudflared
        print("\n1️⃣ Установка cloudflared...")
        stdin, stdout, stderr = ssh.exec_command(
            "which cloudflared || echo 'not found'",
            timeout=10
        )
        cloudflared_check = stdout.read().decode('utf-8').strip()
        
        if "not found" in cloudflared_check:
            print("   📥 Установка cloudflared...")
            commands = [
                "wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /tmp/cloudflared",
                "chmod +x /tmp/cloudflared",
                "mv /tmp/cloudflared /usr/local/bin/cloudflared",
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    print(f"   ✓ {cmd.split()[0]}")
                else:
                    error = stderr.read().decode('utf-8')
                    print(f"   ✗ Ошибка: {error}")
                    return
        else:
            print(f"   ✅ cloudflared уже установлен: {cloudflared_check}")
        
        # 2. Создание systemd сервиса
        print("\n2️⃣ Создание systemd сервиса...")
        service_content = """[Unit]
Description=Cloudflared tunnel for HTTPS webhook
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel --url http://localhost:8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        # Записываем service файл
        sftp = ssh.open_sftp()
        with sftp.file('/tmp/cloudflared-tunnel.service', 'w') as f:
            f.write(service_content)
        sftp.close()
        
        # Копируем в systemd
        stdin, stdout, stderr = ssh.exec_command(
            "mv /tmp/cloudflared-tunnel.service /etc/systemd/system/cloudflared-tunnel.service",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✓ Service файл создан")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ✗ Ошибка: {error}")
            return
        
        # 3. Перезагрузка systemd и запуск
        print("\n3️⃣ Запуск сервиса...")
        commands = [
            "systemctl daemon-reload",
            "systemctl enable cloudflared-tunnel.service",
            "systemctl start cloudflared-tunnel.service",
        ]
        
        for cmd in commands:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print(f"   ✓ {cmd}")
            else:
                error = stderr.read().decode('utf-8')
                print(f"   ⚠️ {cmd}: {error}")
        
        # 4. Получение URL
        print("\n4️⃣ Получение HTTPS URL...")
        time.sleep(3)  # Даем время запуститься
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u cloudflared-tunnel.service -n 20 --no-pager | grep -o 'https://[a-z0-9-]*\\.trycloudflare\\.com' | head -n 1",
            timeout=10
        )
        tunnel_url = stdout.read().decode('utf-8').strip()
        
        if tunnel_url:
            print(f"   ✅ HTTPS URL получен: {tunnel_url}")
            print(f"\n📋 Используйте этот URL в YooKassa:")
            print(f"   {tunnel_url}/webhooks/yookassa")
            print(f"\n⚠️ ВАЖНО: Этот URL изменится при перезагрузке сервера!")
            print(f"   После перезагрузки проверьте URL командой:")
            print(f"   journalctl -u cloudflared-tunnel.service -n 20 | grep trycloudflare")
        else:
            print("   ⚠️ URL пока не получен, проверьте логи:")
            print("   journalctl -u cloudflared-tunnel.service -n 30")
        
        # 5. Проверка статуса
        print("\n5️⃣ Проверка статуса сервиса...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl status cloudflared-tunnel.service --no-pager | head -n 10",
            timeout=10
        )
        status = stdout.read().decode('utf-8')
        print(status)
        
        print("\n" + "="*60)
        print("✅ НАСТРОЙКА ЗАВЕРШЕНА")
        print("="*60)
        print("\n📋 Что сделано:")
        print("✓ cloudflared установлен")
        print("✓ Создан systemd сервис cloudflared-tunnel.service")
        print("✓ Сервис включен в автозапуск")
        print("✓ Сервис запущен")
        print("\n⚠️ Помните:")
        print("   - URL меняется при перезагрузке сервера")
        print("   - Для постоянного URL нужен именованный туннель (cloudflared tunnel create)")
        print("   - Или используйте свой домен с SSL сертификатом")
        
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

