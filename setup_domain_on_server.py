#!/usr/bin/env python3
"""
Настройка домена с SSL на сервере через cli.py
"""
import paramiko
import time
import os
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
DOMAIN = "enneurogpt.dostupnet.ru"
SERVER_DIR = "/opt/gptbot"


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
    print("🌐 Настройка домена с SSL на сервере")
    print("="*60)
    print(f"\n📋 Домен: {DOMAIN}")
    print(f"📋 IP сервера: {SERVER_IP}")
    
    # Проверяем наличие cli.py локально
    local_cli = Path(__file__).parent / "cli.py"
    if not local_cli.exists():
        print(f"❌ Файл cli.py не найден: {local_cli}")
        return
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # 1. Копируем cli.py на сервер
        print("\n1️⃣ Копирование cli.py на сервер...")
        sftp = ssh.open_sftp()
        remote_cli = f"{SERVER_DIR}/cli.py"
        sftp.put(str(local_cli), remote_cli)
        sftp.close()
        print(f"   ✅ cli.py скопирован: {remote_cli}")
        
        # Делаем исполняемым
        ssh.exec_command(f"chmod +x {remote_cli}", timeout=10)
        
        # 2. Проверяем DNS
        print("\n2️⃣ Проверка DNS...")
        stdin, stdout, stderr = ssh.exec_command(
            f"nslookup {DOMAIN} 2>&1 | grep -A 1 'Name:' || dig +short {DOMAIN}",
            timeout=10
        )
        dns_result = stdout.read().decode('utf-8')
        print(f"   DNS результат: {dns_result.strip()}")
        
        if SERVER_IP not in dns_result and "93.88.203.86" not in dns_result:
            print(f"   ⚠️ DNS может быть еще не обновлен, но продолжаем...")
        
        # 3. Устанавливаем nginx если нет
        print("\n3️⃣ Проверка nginx...")
        stdin, stdout, stderr = ssh.exec_command("which nginx || echo 'not found'", timeout=10)
        nginx_check = stdout.read().decode('utf-8').strip()
        
        if "not found" in nginx_check:
            print("   📥 Установка nginx...")
            stdin, stdout, stderr = ssh.exec_command(
                "apt-get update -qq && apt-get install -y nginx",
                timeout=120
            )
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print("   ✅ nginx установлен")
            else:
                error = stderr.read().decode('utf-8')
                print(f"   ⚠️ Ошибка установки nginx: {error}")
        else:
            print(f"   ✅ nginx уже установлен")
        
        # 4. Создаем конфигурацию nginx для домена
        print("\n4️⃣ Создание конфигурации nginx...")
        nginx_config = f"""server {{
    listen 80;
    server_name {DOMAIN};

    location / {{
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты для webhook
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
}}
"""
        
        config_path = f"/etc/nginx/sites-available/{DOMAIN}"
        sftp = ssh.open_sftp()
        with sftp.file(config_path, 'w') as f:
            f.write(nginx_config)
        sftp.close()
        print(f"   ✅ Конфигурация создана: {config_path}")
        
        # Создаем симлинк
        ssh.exec_command(f"ln -sf {config_path} /etc/nginx/sites-enabled/{DOMAIN}", timeout=10)
        ssh.exec_command("rm -f /etc/nginx/sites-enabled/default", timeout=10)
        
        # Проверка и перезапуск nginx
        stdin, stdout, stderr = ssh.exec_command("nginx -t", timeout=10)
        nginx_test = stdout.read().decode('utf-8')
        if "successful" in nginx_test.lower():
            print("   ✅ Конфигурация nginx корректна")
            ssh.exec_command("systemctl restart nginx", timeout=10)
            print("   ✅ nginx перезапущен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ⚠️ Ошибка в конфигурации: {error}")
        
        # 5. Устанавливаем certbot
        print("\n5️⃣ Установка certbot...")
        stdin, stdout, stderr = ssh.exec_command("which certbot || echo 'not found'", timeout=10)
        certbot_check = stdout.read().decode('utf-8').strip()
        
        if "not found" in certbot_check:
            print("   📥 Установка certbot...")
            stdin, stdout, stderr = ssh.exec_command(
                "apt-get install -y certbot python3-certbot-nginx",
                timeout=120
            )
            exit_status = stdout.channel.recv_exit_status()
            if exit_status == 0:
                print("   ✅ certbot установлен")
            else:
                error = stderr.read().decode('utf-8')
                print(f"   ⚠️ Ошибка установки certbot: {error}")
        else:
            print(f"   ✅ certbot уже установлен")
        
        # 6. Получаем SSL сертификат через certbot
        print("\n6️⃣ Получение SSL сертификата...")
        print("   ⏳ Это может занять 1-2 минуты...")
        print("   💡 Certbot автоматически настроит nginx для HTTPS")
        
        # Используем certbot с nginx плагином (автоматически настроит nginx)
        certbot_cmd = f"certbot --nginx -d {DOMAIN} --non-interactive --agree-tos --email admin@{DOMAIN} --redirect"
        
        # Выполняем в интерактивном режиме через SSH сессию
        print(f"\n   📋 Выполняю команду: certbot --nginx -d {DOMAIN}")
        print("   ⏳ Ожидаю завершения...")
        
        stdin, stdout, stderr = ssh.exec_command(certbot_cmd, timeout=180)
        
        # Читаем вывод в реальном времени
        import select
        import sys
        
        output_lines = []
        error_lines = []
        
        # Ждем завершения команды
        while not stdout.channel.exit_status_ready():
            time.sleep(1)
        
        exit_status = stdout.channel.recv_exit_status()
        certbot_output = stdout.read().decode('utf-8')
        certbot_error = stderr.read().decode('utf-8')
        
        print("\n   📋 Вывод certbot:")
        if certbot_output:
            print(certbot_output)
        if certbot_error:
            print(f"   Ошибки: {certbot_error}")
        
        if exit_status == 0:
            print("\n   ✅ SSL сертификат успешно установлен!")
        else:
            print(f"\n   ⚠️ Certbot вернул код: {exit_status}")
            print("   💡 Возможно нужно запустить вручную на сервере:")
            print(f"   certbot --nginx -d {DOMAIN}")
        
        # 7. Проверяем доступность
        print("\n7️⃣ Проверка доступности...")
        time.sleep(3)
        
        # Проверка HTTPS
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTPS: %{{http_code}}\n' https://{DOMAIN}/health",
            timeout=15
        )
        https_code = stdout.read().decode('utf-8').strip()
        print(f"   {https_code}")
        
        webhook_url = f"https://{DOMAIN}/webhooks/yookassa"
        
        print("\n" + "="*60)
        print("✅ НАСТРОЙКА ЗАВЕРШЕНА")
        print("="*60)
        print(f"\n📋 Ваш постоянный HTTPS URL:")
        print(f"   {webhook_url}")
        print(f"\n📋 Используйте этот URL в YooKassa:")
        print(f"   {webhook_url}")
        print(f"\n✅ Преимущества:")
        print(f"   - Постоянный URL (не меняется)")
        print(f"   - SSL сертификат от Let's Encrypt")
        print(f"   - Автоматическое обновление сертификата")
        print(f"\n⚠️ ВАЖНО:")
        print(f"   - Обновите webhook URL в YooKassa на: {webhook_url}")
        print(f"   - Можно отключить cloudflared туннель (больше не нужен)")
        print(f"   - Команда для отключения: systemctl stop cloudflared-tunnel.service")
        
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

