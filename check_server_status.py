#!/usr/bin/env python3
"""Проверка статуса сервера и актуальности кода."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
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
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
        
        print("🔍 Проверка статуса сервера")
        print("="*60)
        
        # Проверяем учетные данные YooKassa
        print("\n📋 Учетные данные YooKassa в .env:")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -E 'YOOKASSA_(SHOP_ID|SECRET_KEY)' {SERVER_DIR}/.env",
            timeout=10
        )
        yookassa_vars = stdout.read().decode('utf-8')
        if yookassa_vars:
            for line in yookassa_vars.strip().split('\n'):
                if 'SECRET_KEY' in line:
                    # Скрываем секретный ключ
                    parts = line.split('=')
                    if len(parts) == 2:
                        key = parts[0]
                        value = parts[1]
                        if len(value) > 25:
                            masked = value[:25] + "..." + value[-5:] if len(value) > 30 else value[:25] + "..."
                            print(f"  {key}={masked}")
                        else:
                            print(f"  {line}")
                else:
                    print(f"  {line}")
        else:
            print("  ⚠️ Не найдены переменные YooKassa")
        
        # Проверяем статус сервисов
        print("\n📊 Статус сервисов:")
        stdin, stdout, stderr = ssh.exec_command(
            'systemctl status gptbot-api.service gptbot-bot.service --no-pager | grep -E "(Active:|Main PID:)"',
            timeout=10
        )
        services_status = stdout.read().decode('utf-8')
        print(services_status)
        
        # Проверяем последние изменения в коде
        print("\n📁 Последние изменения в коде:")
        stdin, stdout, stderr = ssh.exec_command(
            f"cd {SERVER_DIR} && find . -name '*.py' -type f -mtime -1 | head -10",
            timeout=10
        )
        recent_files = stdout.read().decode('utf-8')
        if recent_files.strip():
            print("  Недавно измененные файлы:")
            for line in recent_files.strip().split('\n'):
                if line:
                    print(f"    {line}")
        else:
            print("  Нет недавно измененных файлов")
        
        # Проверяем версию Python и зависимости
        print("\n🐍 Версия Python и ключевые зависимости:")
        stdin, stdout, stderr = ssh.exec_command(
            f"cd {SERVER_DIR} && source venv/bin/activate && python --version && pip list | grep -E '(httpx|yookassa|openai)'",
            timeout=10
        )
        python_info = stdout.read().decode('utf-8')
        print(python_info)
        
        # Проверяем логи на ошибки
        print("\n📋 Последние ошибки в логах (если есть):")
        stdin, stdout, stderr = ssh.exec_command(
            'journalctl -u gptbot-api.service -u gptbot-bot.service --since "5 minutes ago" --no-pager | grep -i error | tail -5',
            timeout=10
        )
        errors = stdout.read().decode('utf-8')
        if errors.strip():
            print(errors)
        else:
            print("  ✓ Ошибок не найдено")
        
        print("\n" + "="*60)
        print("✅ Проверка завершена")
        
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

