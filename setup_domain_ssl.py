#!/usr/bin/env python3
"""
Настройка домена с SSL сертификатом для постоянного HTTPS URL.
"""
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
    print("🌐 Настройка домена с SSL сертификатом")
    print("="*60)
    print(f"\n📋 Домен: {DOMAIN}")
    print(f"📋 IP сервера: {SERVER_IP}")
    
    print("\n⚠️ ПЕРЕД НАЧАЛОМ:")
    print("1. Убедитесь, что DNS запись для домена настроена:")
    print(f"   Тип: A")
    print(f"   Имя: enneurogpt (или @ для корневого домена)")
    print(f"   Значение: {SERVER_IP}")
    print(f"   TTL: 300 (или меньше)")
    print("\n2. Проверьте, что домен указывает на сервер:")
    print(f"   nslookup {DOMAIN}")
    print(f"   Должен вернуть: {SERVER_IP}")
    
    input("\nНажмите Enter когда DNS настроен, или Ctrl+C для отмены...")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # 1. Проверка DNS
        print("\n1️⃣ Проверка DNS...")
        stdin, stdout, stderr = ssh.exec_command(f"nslookup {DOMAIN} | grep -A 1 'Name:'", timeout=10)
        dns_result = stdout.read().decode('utf-8')
        if SERVER_IP in dns_result or DOMAIN in dns_result:
            print(f"   ✅ DNS настроен")
        else:
            print(f"   ⚠️ DNS может быть еще не обновлен")
            print(f"   Результат: {dns_result}")
        
        # 2. Установка nginx
        print("\n2️⃣ Установка nginx...")
        stdin, stdout, stderr = ssh.exec_command("which nginx || echo 'not found'", timeout=10)
        nginx_check = stdout.read().decode('utf-8').strip()
        
        if "not found" in nginx_check:
            print("   📥 Установка nginx...")
            commands = [
                "apt-get update -qq",
                "apt-get install -y nginx",
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=60)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    print(f"   ✓ {cmd.split()[0]}")
                else:
                    error = stderr.read().decode('utf-8')
                    print(f"   ✗ Ошибка: {error}")
                    if "apt-get" in cmd:
                        print("   Попробуйте установить nginx вручную")
        else:
            print(f"   ✅ nginx уже установлен: {nginx_check}")
        
        # 3. Создание конфигурации nginx
        print("\n3️⃣ Создание конфигурации nginx...")
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
        
        sftp = ssh.open_sftp()
        config_path = f"/etc/nginx/sites-available/{DOMAIN}"
        with sftp.file(config_path, 'w') as f:
            f.write(nginx_config)
        sftp.close()
        print(f"   ✓ Конфигурация создана: {config_path}")
        
        # Создаем симлинк
        stdin, stdout, stderr = ssh.exec_command(
            f"ln -sf {config_path} /etc/nginx/sites-enabled/{DOMAIN}",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print(f"   ✓ Симлинк создан")
        
        # Удаляем дефолтный конфиг если есть
        ssh.exec_command("rm -f /etc/nginx/sites-enabled/default", timeout=10)
        
        # Проверка конфигурации
        stdin, stdout, stderr = ssh.exec_command("nginx -t", timeout=10)
        nginx_test = stdout.read().decode('utf-8')
        if "successful" in nginx_test.lower():
            print("   ✅ Конфигурация nginx корректна")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ⚠️ Ошибка в конфигурации: {error}")
        
        # Перезапуск nginx
        stdin, stdout, stderr = ssh.exec_command("systemctl restart nginx", timeout=10)
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✅ nginx перезапущен")
        else:
            error = stderr.read().decode('utf-8')
            print(f"   ✗ Ошибка перезапуска: {error}")
        
        # 4. Установка certbot
        print("\n4️⃣ Установка certbot для SSL...")
        stdin, stdout, stderr = ssh.exec_command("which certbot || echo 'not found'", timeout=10)
        certbot_check = stdout.read().decode('utf-8').strip()
        
        if "not found" in certbot_check:
            print("   📥 Установка certbot...")
            commands = [
                "apt-get install -y certbot python3-certbot-nginx",
            ]
            
            for cmd in commands:
                stdin, stdout, stderr = ssh.exec_command(cmd, timeout=120)
                exit_status = stdout.channel.recv_exit_status()
                if exit_status == 0:
                    print(f"   ✓ certbot установлен")
                else:
                    error = stderr.read().decode('utf-8')
                    print(f"   ✗ Ошибка: {error}")
        else:
            print(f"   ✅ certbot уже установлен: {certbot_check}")
        
        # 5. Получение SSL сертификата
        print("\n5️⃣ Получение SSL сертификата...")
        print("   ⏳ Это может занять 1-2 минуты...")
        
        # Certbot в неинтерактивном режиме
        certbot_cmd = f"certbot --nginx -d {DOMAIN} --non-interactive --agree-tos --email admin@{DOMAIN} --redirect"
        stdin, stdout, stderr = ssh.exec_command(certbot_cmd, timeout=180)
        exit_status = stdout.channel.recv_exit_status()
        
        certbot_output = stdout.read().decode('utf-8')
        certbot_error = stderr.read().decode('utf-8')
        
        if exit_status == 0 and "Successfully" in certbot_output:
            print("   ✅ SSL сертификат успешно установлен!")
            print(f"   ✅ HTTPS доступен: https://{DOMAIN}")
        else:
            print("   ⚠️ Возможна ошибка при получении сертификата")
            print(f"   Вывод: {certbot_output}")
            if certbot_error:
                print(f"   Ошибки: {certbot_error}")
            print("\n   💡 Попробуйте запустить вручную:")
            print(f"   certbot --nginx -d {DOMAIN}")
        
        # 6. Настройка автообновления сертификата
        print("\n6️⃣ Настройка автообновления SSL сертификата...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl enable certbot.timer && systemctl start certbot.timer",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        if exit_status == 0:
            print("   ✅ Автообновление сертификата настроено")
        
        # 7. Проверка доступности
        print("\n7️⃣ Проверка доступности...")
        time.sleep(3)
        
        # Проверка HTTP
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTP: %{{http_code}}\n' http://{DOMAIN}/health",
            timeout=10
        )
        http_code = stdout.read().decode('utf-8').strip()
        print(f"   HTTP: {http_code}")
        
        # Проверка HTTPS
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w 'HTTPS: %{{http_code}}\n' https://{DOMAIN}/health",
            timeout=10
        )
        https_code = stdout.read().decode('utf-8').strip()
        print(f"   HTTPS: {https_code}")
        
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
        print(f"   - SSL сертификат от Let's Encrypt (бесплатный)")
        print(f"   - Автоматическое обновление сертификата")
        print(f"   - Не зависит от cloudflared")
        
        print(f"\n⚠️ ВАЖНО:")
        print(f"   - Обновите webhook URL в YooKassa на новый: {webhook_url}")
        print(f"   - Можно отключить cloudflared туннель (больше не нужен)")
        
    except KeyboardInterrupt:
        print("\n\n❌ Прервано пользователем")
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

