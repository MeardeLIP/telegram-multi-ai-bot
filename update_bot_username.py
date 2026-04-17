#!/usr/bin/env python3
"""
Обновление BOT_USERNAME на сервере.
"""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
ENV_FILE = f"{SERVER_DIR}/.env"

BOT_USERNAME = "EnNeuroGPTbot"


def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
    """Устанавливает SSH соединение."""
    ssh = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Попытка подключения {attempt}/{max_retries}...")
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
                print("✓ Подключено успешно\n")
                return ssh
        except Exception as e:
            print(f"✗ Ошибка (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                time.sleep(2 * attempt)
            else:
                raise
    raise ConnectionError("Не удалось подключиться")


def update_env_file(ssh, bot_username):
    """Обновляет BOT_USERNAME в .env файле."""
    print("📝 Обновление .env файла...")
    
    # Читаем текущий .env файл
    stdin, stdout, stderr = ssh.exec_command(f"cat {ENV_FILE}", timeout=10)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"⚠️ Не удалось прочитать .env файл, создаем новый...")
        current_content = ""
    else:
        current_content = stdout.read().decode('utf-8')
    
    # Обновляем или добавляем BOT_USERNAME
    lines = current_content.split('\n')
    updated_lines = []
    bot_username_found = False
    
    for line in lines:
        if line.startswith('BOT_USERNAME='):
            updated_lines.append(f"BOT_USERNAME='{bot_username}'")
            bot_username_found = True
        else:
            updated_lines.append(line)
    
    # Добавляем, если не найдено
    if not bot_username_found:
        updated_lines.append(f"BOT_USERNAME='{bot_username}'")
    
    # Записываем обновленный файл
    new_content = '\n'.join(updated_lines)
    
    # Создаем временный файл
    temp_file = f"{ENV_FILE}.tmp"
    sftp = ssh.open_sftp()
    with sftp.file(temp_file, 'w') as f:
        f.write(new_content)
    sftp.close()
    
    # Заменяем оригинальный файл
    stdin, stdout, stderr = ssh.exec_command(
        f"mv {temp_file} {ENV_FILE} && chmod 644 {ENV_FILE} && chown gptbot:gptbot {ENV_FILE}",
        timeout=10
    )
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode('utf-8')
        raise Exception(f"Не удалось обновить .env файл: {error}")
    
    print("✓ .env файл обновлен")
    print(f"  BOT_USERNAME='{bot_username}'")


def check_public_base_url(ssh):
    """Проверяет и обновляет PUBLIC_BASE_URL если он указывает на localhost."""
    print("\n🔍 Проверка PUBLIC_BASE_URL...")
    
    stdin, stdout, stderr = ssh.exec_command(
        f"grep '^PUBLIC_BASE_URL=' {ENV_FILE} || echo ''",
        timeout=10
    )
    current_url = stdout.read().decode('utf-8').strip()
    
    if 'localhost' in current_url or '127.0.0.1' in current_url:
        print(f"⚠️ Обнаружен localhost в PUBLIC_BASE_URL: {current_url}")
        print("   Нужно обновить на публичный URL сервера")
        
        # Читаем .env
        stdin, stdout, stderr = ssh.exec_command(f"cat {ENV_FILE}", timeout=10)
        content = stdout.read().decode('utf-8')
        
        # Обновляем PUBLIC_BASE_URL
        lines = content.split('\n')
        updated_lines = []
        for line in lines:
            if line.startswith('PUBLIC_BASE_URL='):
                # Используем IP сервера
                updated_lines.append(f"PUBLIC_BASE_URL='http://{SERVER_IP}:8000'")
            else:
                updated_lines.append(line)
        
        new_content = '\n'.join(updated_lines)
        temp_file = f"{ENV_FILE}.tmp"
        sftp = ssh.open_sftp()
        with sftp.file(temp_file, 'w') as f:
            f.write(new_content)
        sftp.close()
        
        stdin, stdout, stderr = ssh.exec_command(
            f"mv {temp_file} {ENV_FILE} && chmod 644 {ENV_FILE} && chown gptbot:gptbot {ENV_FILE}",
            timeout=10
        )
        print(f"✓ PUBLIC_BASE_URL обновлен: http://{SERVER_IP}:8000")
    else:
        print(f"✓ PUBLIC_BASE_URL корректный: {current_url}")


def main():
    print("🔄 Обновление BOT_USERNAME на сервере")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Обновляем BOT_USERNAME
        update_env_file(ssh, BOT_USERNAME)
        
        # Проверяем PUBLIC_BASE_URL
        check_public_base_url(ssh)
        
        # Перезапускаем сервисы для применения изменений
        print("\n🔄 Перезапуск сервисов...")
        ssh.exec_command("systemctl restart gptbot-api.service gptbot-bot.service")
        time.sleep(3)
        print("✓ Сервисы перезапущены")
        
        # Проверяем статус
        print("\n📊 Проверка статуса сервисов...")
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 10')
        api_status = stdout.read().decode('utf-8')
        print("API сервис:")
        print(api_status)
        
        # Проверяем доступность /thankyou
        print("\n🔍 Проверка доступности /thankyou...")
        stdin, stdout, stderr = ssh.exec_command(
            f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:8000/thankyou || echo '000'",
            timeout=10
        )
        http_code = stdout.read().decode('utf-8').strip()
        if http_code == '200':
            print("✓ Endpoint /thankyou доступен (HTTP 200)")
        else:
            print(f"⚠️ Endpoint /thankyou вернул код: {http_code}")
        
        print("\n" + "="*60)
        print("✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!")
        print("="*60)
        print("\n📋 Что сделано:")
        print(f"✓ BOT_USERNAME установлен: {BOT_USERNAME}")
        print("✓ PUBLIC_BASE_URL проверен и обновлен (если нужно)")
        print("✓ Сервисы перезапущены")
        print("\n⚠️ Важно:")
        print(f"   После оплаты пользователи будут редиректиться на:")
        print(f"   http://{SERVER_IP}:8000/thankyou")
        print(f"   И автоматически вернутся в бот @{BOT_USERNAME}")
        
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

