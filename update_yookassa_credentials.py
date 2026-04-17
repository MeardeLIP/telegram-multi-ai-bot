#!/usr/bin/env python3
"""
Обновление учетных данных YooKassa на сервере.
"""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
ENV_FILE = f"{SERVER_DIR}/.env"

YOOKASSA_SHOP_ID = "1221301"  # Это ACCOUNT_ID из запроса пользователя
YOOKASSA_SECRET_KEY = "live_SDCkzgDi4s9VXDi3zBVBOOEzl16NJ11jCtqX-fmMsEg"


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


def update_env_file(ssh, shop_id, secret_key):
    """Обновляет учетные данные YooKassa в .env файле."""
    print("📝 Обновление .env файла...")
    
    # Читаем текущий .env файл
    stdin, stdout, stderr = ssh.exec_command(f"cat {ENV_FILE}", timeout=10)
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        print(f"⚠️ Не удалось прочитать .env файл, создаем новый...")
        current_content = ""
    else:
        current_content = stdout.read().decode('utf-8')
    
    # Обновляем или добавляем YOOKASSA_SHOP_ID (или YOOKASSA_ACCOUNT_ID)
    lines = current_content.split('\n')
    updated_lines = []
    yookassa_shop_id_found = False
    yookassa_secret_key_found = False
    
    for line in lines:
        # Проверяем оба варианта названия
        if line.startswith('YOOKASSA_SHOP_ID=') or line.startswith('YOOKASSA_ACCOUNT_ID='):
            updated_lines.append(f"YOOKASSA_SHOP_ID='{shop_id}'")
            yookassa_shop_id_found = True
        elif line.startswith('YOOKASSA_SECRET_KEY='):
            updated_lines.append(f"YOOKASSA_SECRET_KEY='{secret_key}'")
            yookassa_secret_key_found = True
        else:
            updated_lines.append(line)
    
    # Добавляем, если не найдены
    if not yookassa_shop_id_found:
        updated_lines.append(f"YOOKASSA_SHOP_ID='{shop_id}'")
    if not yookassa_secret_key_found:
        updated_lines.append(f"YOOKASSA_SECRET_KEY='{secret_key}'")
    
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
        f"mv {temp_file} {ENV_FILE} && chmod 600 {ENV_FILE}",
        timeout=10
    )
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode('utf-8')
        raise Exception(f"Не удалось обновить .env файл: {error}")
    
    print("✓ .env файл обновлен")
    
    # Показываем обновленные значения (без секретного ключа полностью)
    print(f"  YOOKASSA_SHOP_ID='{shop_id}'")
    print(f"  YOOKASSA_SECRET_KEY='{secret_key[:20]}...' (скрыт)")


def main():
    print("🔄 Обновление учетных данных YooKassa")
    print("="*60)
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Обновляем .env файл
        update_env_file(ssh, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)
        
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
        
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-bot.service --no-pager | head -n 10')
        bot_status = stdout.read().decode('utf-8')
        print("\nBot сервис:")
        print(bot_status)
        
        print("\n" + "="*60)
        print("✅ УЧЕТНЫЕ ДАННЫЕ YOOKASSA ОБНОВЛЕНЫ!")
        print("="*60)
        print("\n📋 Что сделано:")
        print(f"✓ YOOKASSA_SHOP_ID обновлен: {YOOKASSA_SHOP_ID}")
        print(f"✓ YOOKASSA_SECRET_KEY обновлен")
        print("✓ Сервисы перезапущены")
        
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

