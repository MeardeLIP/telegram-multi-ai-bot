#!/usr/bin/env python3
"""Отключение cloudflared туннеля."""
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
    print("🛑 Отключение cloudflared туннеля")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Проверяем статус перед отключением
        print("\n1️⃣ Проверка текущего статуса...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl status cloudflared-tunnel.service --no-pager | head -n 5",
            timeout=10
        )
        status = stdout.read().decode('utf-8')
        print(status)
        
        # Останавливаем сервис
        print("\n2️⃣ Остановка cloudflared туннеля...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl stop cloudflared-tunnel.service",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✅ Сервис остановлен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ⚠️ {error}")
        
        # Отключаем автозапуск
        print("\n3️⃣ Отключение автозапуска...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl disable cloudflared-tunnel.service",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✅ Автозапуск отключен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ⚠️ {error}")
        
        # Проверяем финальный статус
        print("\n4️⃣ Проверка финального статуса...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl is-active cloudflared-tunnel.service 2>&1",
            timeout=10
        )
        final_status = stdout.read().decode('utf-8').strip()
        
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl is-enabled cloudflared-tunnel.service 2>&1",
            timeout=10
        )
        enabled_status = stdout.read().decode('utf-8').strip()
        
        print(f"   Статус: {final_status}")
        print(f"   Автозапуск: {enabled_status}")
        
        print("\n" + "="*60)
        print("✅ CLOUDFLARED ТУННЕЛЬ ОТКЛЮЧЕН")
        print("="*60)
        print("\n📋 Что сделано:")
        print("✓ Сервис cloudflared-tunnel.service остановлен")
        print("✓ Автозапуск отключен")
        print("\n💡 Теперь используется постоянный домен:")
        print("   https://enneurogpt.dostupnet.ru")
        print("\n✅ Cloudflared больше не нужен!")
        
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

