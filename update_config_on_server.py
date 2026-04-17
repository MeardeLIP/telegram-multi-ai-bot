#!/usr/bin/env python3
"""Обновление app/config.py на сервере."""
import paramiko
import time
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
LOCAL_CONFIG = Path(__file__).parent / "app" / "config.py"
REMOTE_CONFIG = f"{SERVER_DIR}/app/config.py"


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


def main():
    print("🔄 Обновление app/config.py на сервере")
    print("="*60)
    
    if not LOCAL_CONFIG.exists():
        print(f"❌ Локальный файл не найден: {LOCAL_CONFIG}")
        return
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        # Копируем файл
        print(f"📤 Копирование {LOCAL_CONFIG.name} на сервер...")
        sftp = ssh.open_sftp()
        
        # Создаем директорию если нужно
        ssh.exec_command(f"mkdir -p {SERVER_DIR}/app")
        
        # Копируем файл
        sftp.put(str(LOCAL_CONFIG), REMOTE_CONFIG)
        sftp.close()
        print(f"✓ Файл скопирован: {REMOTE_CONFIG}")
        
        # Проверяем, что bot_username есть в файле
        print("\n🔍 Проверка наличия bot_username в config.py...")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep 'bot_username' {REMOTE_CONFIG}",
            timeout=10
        )
        grep_result = stdout.read().decode('utf-8')
        if grep_result:
            print("✓ Поле bot_username найдено:")
            print(f"  {grep_result.strip()}")
        else:
            print("⚠️ Поле bot_username не найдено!")
        
        # Перезапускаем API сервис
        print("\n🔄 Перезапуск API сервиса...")
        ssh.exec_command("systemctl restart gptbot-api.service")
        time.sleep(3)
        print("✓ API сервис перезапущен")
        
        # Проверяем статус
        print("\n📊 Проверка статуса API сервиса...")
        stdin, stdout, stderr = ssh.exec_command('systemctl status gptbot-api.service --no-pager | head -n 10')
        status = stdout.read().decode('utf-8')
        print(status)
        
        # Проверяем /thankyou
        print("\n🔍 Проверка endpoint /thankyou...")
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command(
            "curl -s -o /dev/null -w 'HTTP Status: %{http_code}\n' http://localhost:8000/thankyou",
            timeout=10
        )
        http_code = stdout.read().decode('utf-8').strip()
        if http_code == '200':
            print("✅ Endpoint /thankyou работает! (HTTP 200)")
        else:
            print(f"⚠️ Endpoint /thankyou вернул код: {http_code}")
            print("   Проверьте логи: journalctl -u gptbot-api.service -n 20")
        
        print("\n" + "="*60)
        print("✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО!")
        print("="*60)
        
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

