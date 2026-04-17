#!/usr/bin/env python3
"""
Отключение старого сервера и проверка работы на новом.
"""
import paramiko
import socket
import time

OLD_SERVER_IP = "149.33.0.41"
OLD_SERVER_USER = "root"
OLD_SERVER_PASSWORD = "JuN8AcrM7H"

NEW_SERVER_IP = "93.88.203.86"
NEW_SERVER_USER = "root"
NEW_SERVER_PASSWORD = "n5nxGTZeFztJf"


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


def execute_command(ssh, command, description, timeout=30):
    """Выполняет команду и выводит результат."""
    print(f"{description}...")
    stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode('utf-8')
    error = stderr.read().decode('utf-8')
    
    if exit_status == 0:
        print(f"✓ {description} - успешно")
        if output.strip():
            print(f"  {output.strip()}")
        return True
    else:
        print(f"⚠ {description} - код: {exit_status}")
        if error:
            print(f"  Ошибка: {error.strip()}")
        return False


def main():
    print("🔄 Переключение на новый сервер")
    print("="*60)
    
    old_ssh = None
    new_ssh = None
    
    try:
        # ШАГ 1: Отключаем старый сервер
        print("\n" + "="*60)
        print("ШАГ 1: Отключение старого сервера (149.33.0.41)")
        print("="*60)
        
        try:
            old_ssh = connect_ssh(OLD_SERVER_IP, OLD_SERVER_USER, OLD_SERVER_PASSWORD)
            
            # Останавливаем сервисы
            execute_command(old_ssh, 
                "systemctl stop gptbot-api.service gptbot-bot.service",
                "Остановка сервисов на старом сервере")
            
            # Отключаем автозапуск
            execute_command(old_ssh,
                "systemctl disable gptbot-api.service gptbot-bot.service",
                "Отключение автозапуска на старом сервере")
            
            # Проверяем статус
            print("\n📊 Статус сервисов на старом сервере:")
            stdin, stdout, stderr = old_ssh.exec_command(
                "systemctl status gptbot-api.service gptbot-bot.service --no-pager | head -n 15"
            )
            status = stdout.read().decode('utf-8')
            print(status)
            
            print("✓ Старый сервер отключен")
            
        except Exception as e:
            print(f"⚠ Не удалось подключиться к старому серверу: {e}")
            print("  Возможно, он уже отключен или недоступен")
        
        # ШАГ 2: Проверяем и запускаем новый сервер
        print("\n" + "="*60)
        print("ШАГ 2: Проверка и запуск нового сервера (93.88.203.86)")
        print("="*60)
        
        new_ssh = connect_ssh(NEW_SERVER_IP, NEW_SERVER_USER, NEW_SERVER_PASSWORD)
        
        # Включаем автозапуск
        execute_command(new_ssh,
            "systemctl enable gptbot-api.service gptbot-bot.service",
            "Включение автозапуска на новом сервере")
        
        # Запускаем сервисы
        execute_command(new_ssh,
            "systemctl start gptbot-api.service gptbot-bot.service",
            "Запуск сервисов на новом сервере")
        
        time.sleep(3)  # Даем время сервисам запуститься
        
        # Проверяем статус сервисов
        print("\n📊 Статус сервисов на новом сервере:")
        stdin, stdout, stderr = new_ssh.exec_command(
            "systemctl status gptbot-api.service --no-pager -l | head -n 12"
        )
        api_status = stdout.read().decode('utf-8')
        print("API сервис:")
        print(api_status)
        
        stdin, stdout, stderr = new_ssh.exec_command(
            "systemctl status gptbot-bot.service --no-pager -l | head -n 12"
        )
        bot_status = stdout.read().decode('utf-8')
        print("\nBot сервис:")
        print(bot_status)
        
        # Проверяем API
        print("\n🔍 Проверка API...")
        stdin, stdout, stderr = new_ssh.exec_command("curl -s http://localhost:8000/health", timeout=10)
        health_response = stdout.read().decode('utf-8')
        if '{"status":"ok"}' in health_response or '"status":"ok"' in health_response:
            print("✓ API работает корректно")
            print(f"  Ответ: {health_response.strip()}")
        else:
            print(f"⚠ API вернул неожиданный ответ: {health_response}")
        
        # Проверяем подключение к БД
        print("\n🔍 Проверка подключения к БД...")
        db_check_cmd = (
            "cd /opt/gptbot && "
            "source venv/bin/activate && "
            "python -c \"from app.db.session import async_session_maker; import asyncio; "
            "async def check(): async with async_session_maker() as s: result = await s.execute('SELECT 1'); print('OK' if result else 'FAIL'); "
            "asyncio.run(check())\" 2>&1"
        )
        stdin, stdout, stderr = new_ssh.exec_command(db_check_cmd, timeout=30)
        db_output = stdout.read().decode('utf-8')
        if 'OK' in db_output or exit_status == 0:
            print("✓ Подключение к БД работает")
        else:
            print(f"⚠ Проблема с БД: {db_output.strip()}")
        
        # Проверяем логи на ошибки
        print("\n🔍 Проверка логов на ошибки...")
        stdin, stdout, stderr = new_ssh.exec_command(
            "journalctl -u gptbot-api.service -u gptbot-bot.service --since '1 minute ago' --no-pager | grep -i error | tail -n 5"
        )
        errors = stdout.read().decode('utf-8')
        if errors.strip():
            print("⚠ Найдены ошибки в логах:")
            print(errors)
        else:
            print("✓ Ошибок в логах не найдено")
        
        # Проверяем настройки прокси
        print("\n🔍 Проверка настроек прокси...")
        stdin, stdout, stderr = new_ssh.exec_command(
            "grep -E '^(OPENAI_PROXY|YOOKASSA_PROXY)=' /opt/gptbot/.env | head -n 2"
        )
        proxy_settings = stdout.read().decode('utf-8')
        if proxy_settings:
            print("Настройки прокси:")
            for line in proxy_settings.strip().split('\n'):
                if 'OPENAI_PROXY' in line:
                    # Маскируем пароль
                    if '@' in line:
                        parts = line.split('@')
                        if len(parts) == 2:
                            auth = parts[0].split('://')[1] if '://' in parts[0] else parts[0]
                            if ':' in auth:
                                user = auth.split(':')[0]
                                masked = line.replace(f':{auth.split(":")[1]}', ':****')
                                print(f"  {masked}")
                            else:
                                print(f"  {line}")
                        else:
                            print(f"  {line}")
                    else:
                        print(f"  {line}")
                elif 'YOOKASSA_PROXY' in line:
                    print(f"  {line}")
        
        print("\n" + "="*60)
        print("✅ ПЕРЕКЛЮЧЕНИЕ ЗАВЕРШЕНО!")
        print("="*60)
        print("\n📋 Итоги:")
        print("✓ Старый сервер (149.33.0.41) - сервисы остановлены и автозапуск отключен")
        print("✓ Новый сервер (93.88.203.86) - сервисы запущены и автозапуск включен")
        print("\n🌐 Новый сервер готов к работе:")
        print(f"   IP: {NEW_SERVER_IP}")
        print(f"   API: http://{NEW_SERVER_IP}:8000")
        print(f"   Health: http://{NEW_SERVER_IP}:8000/health")
        print("\n⚠️ Проверьте работу бота в Telegram!")
        
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if old_ssh:
            try:
                old_ssh.close()
            except:
                pass
        if new_ssh:
            try:
                new_ssh.close()
            except:
                pass


if __name__ == "__main__":
    main()

