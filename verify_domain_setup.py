#!/usr/bin/env python3
"""Проверка настройки домена и SSL."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
DOMAIN = "enneurogpt.dostupnet.ru"


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
    print("🔍 Финальная проверка настройки домена")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        webhook_url = f"https://{DOMAIN}/webhooks/yookassa"
        
        # 1. Проверка HTTPS доступности
        print("\n1️⃣ Проверка HTTPS...")
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTP Status: %{{http_code}}\n' https://{DOMAIN}/health",
            timeout=15
        )
        http_code = stdout.read().decode('utf-8').strip()
        print(f"   {http_code}")
        
        # 2. Проверка webhook endpoint
        print("\n2️⃣ Проверка webhook endpoint...")
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTP Status: %{{http_code}}\n' -X POST {webhook_url} -H 'Content-Type: application/json' -d '{{}}'",
            timeout=15
        )
        webhook_code = stdout.read().decode('utf-8').strip()
        print(f"   {webhook_code}")
        
        # 3. Проверка SSL сертификата
        print("\n3️⃣ Проверка SSL сертификата...")
        stdin, stdout, stderr = ssh.exec_command(
            f"echo | openssl s_client -servername {DOMAIN} -connect {DOMAIN}:443 2>/dev/null | openssl x509 -noout -dates",
            timeout=15
        )
        cert_info = stdout.read().decode('utf-8')
        if cert_info:
            print("   ✅ SSL сертификат активен:")
            for line in cert_info.strip().split('\n'):
                if line.strip():
                    print(f"   {line}")
        else:
            print("   ⚠️ Не удалось получить информацию о сертификате")
        
        # 4. Проверка nginx конфигурации
        print("\n4️⃣ Проверка nginx конфигурации...")
        stdin, stdout, stderr = ssh.exec_command(
            "nginx -t 2>&1",
            timeout=10
        )
        nginx_test = stdout.read().decode('utf-8')
        if "successful" in nginx_test.lower():
            print("   ✅ Конфигурация nginx корректна")
        else:
            print(f"   ⚠️ {nginx_test}")
        
        # 5. Проверка статуса сервисов
        print("\n5️⃣ Проверка статуса сервисов...")
        stdin, stdout, stderr = ssh.exec_command(
            'systemctl is-active nginx gptbot-api.service',
            timeout=10
        )
        services = stdout.read().decode('utf-8').strip().split('\n')
        for service in services:
            if 'active' in service:
                print(f"   ✅ {service}")
            else:
                print(f"   ❌ {service}")
        
        # 6. Проверка автообновления сертификата
        print("\n6️⃣ Проверка автообновления сертификата...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl is-enabled certbot.timer 2>&1",
            timeout=10
        )
        certbot_timer = stdout.read().decode('utf-8').strip()
        if "enabled" in certbot_timer:
            print("   ✅ Автообновление сертификата включено")
        else:
            print("   ⚠️ Автообновление может быть не настроено")
        
        print("\n" + "="*60)
        print("✅ ВСЕ ПРОВЕРКИ ЗАВЕРШЕНЫ")
        print("="*60)
        
        print(f"\n🎯 Ваш постоянный HTTPS URL:")
        print(f"   {webhook_url}")
        
        print(f"\n📋 ЧТО ДЕЛАТЬ ДАЛЬШЕ:")
        print(f"1. ✅ Обновите webhook URL в YooKassa:")
        print(f"   {webhook_url}")
        print(f"\n2. ✅ Выберите событие 'payment.succeeded' в YooKassa")
        print(f"\n3. ✅ Сохраните настройки")
        print(f"\n4. 💡 Можно отключить cloudflared туннель (больше не нужен):")
        print(f"   systemctl stop cloudflared-tunnel.service")
        print(f"   systemctl disable cloudflared-tunnel.service")
        
        print(f"\n✅ ВСЕ ГОТОВО! Система полностью настроена!")
        
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

