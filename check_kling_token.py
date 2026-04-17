#!/usr/bin/env python3
"""Диагностический скрипт для проверки загрузки токена KLING API на сервере."""
import paramiko
import time

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
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
    password = input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, password)
        
        print("🔍 Диагностика токена KLING API на сервере")
        print("="*60)
        
        env_file = f"{SERVER_DIR}/.env"
        
        # 1. Проверка наличия .env файла
        print("\n📁 Проверка .env файла:")
        stdin, stdout, stderr = ssh.exec_command(
            f"test -f {env_file} && echo 'exists' || echo 'not_found'",
            timeout=10
        )
        file_exists = stdout.read().decode('utf-8').strip() == "exists"
        if file_exists:
            print(f"  ✓ Файл {env_file} существует")
        else:
            print(f"  ✗ Файл {env_file} НЕ НАЙДЕН!")
            return
        
        # 2. Проверка переменной KLING_ACCESS_KEY в .env
        print("\n🔑 Проверка KLING_ACCESS_KEY в .env файле:")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -E '^KLING_ACCESS_KEY=' {env_file} 2>/dev/null || echo 'NOT_FOUND'",
            timeout=10
        )
        env_line = stdout.read().decode('utf-8').strip()
        
        if env_line == "NOT_FOUND" or not env_line:
            print("  ✗ KLING_ACCESS_KEY НЕ НАЙДЕН в .env файле!")
        else:
            # Извлекаем значение
            if '=' in env_line:
                key, value = env_line.split('=', 1)
                value = value.strip().strip('"').strip("'")
                
                if not value:
                    print("  ✗ KLING_ACCESS_KEY найден, но значение ПУСТОЕ!")
                else:
                    token_length = len(value)
                    token_preview = f"{value[:4]}...{value[-4:]}" if token_length > 8 else "***"
                    print(f"  ✓ KLING_ACCESS_KEY найден в .env")
                    print(f"    Длина: {token_length} символов")
                    print(f"    Превью: {token_preview}")
                    
                    if token_length < 10:
                        print(f"    ⚠️ ВНИМАНИЕ: Токен слишком короткий (меньше 10 символов)!")
        
        # 3. Проверка других KLING переменных
        print("\n🔧 Проверка других KLING переменных:")
        kling_vars = {
            "KLING_SECRET_KEY": "SECRET",
            "KLING_API_ID": "ID",
            "KLING_API_BASE_URL": "URL"
        }
        
        for var_name, var_type in kling_vars.items():
            stdin, stdout, stderr = ssh.exec_command(
                f"grep -E '^{var_name}=' {env_file} 2>/dev/null | cut -d'=' -f2- || echo 'NOT_FOUND'",
                timeout=10
            )
            value = stdout.read().decode('utf-8').strip().strip('"').strip("'")
            
            if value == "NOT_FOUND" or not value:
                print(f"  ✗ {var_name} - НЕ НАЙДЕН")
            else:
                if var_type == "SECRET":
                    masked = value[:10] + "..." + value[-5:] if len(value) > 15 else "***"
                    print(f"  ✓ {var_name}={masked} (длина: {len(value)})")
                else:
                    print(f"  ✓ {var_name}={value}")
        
        # 4. Проверка загрузки токена в запущенном процессе бота
        print("\n🤖 Проверка загрузки токена в процессе бота:")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl status gptbot-bot.service --no-pager | grep -E '(Active|Main PID)' || echo 'SERVICE_NOT_FOUND'",
            timeout=10
        )
        service_status = stdout.read().decode('utf-8').strip()
        
        if "SERVICE_NOT_FOUND" in service_status or "inactive" in service_status.lower():
            print("  ⚠️ Сервис gptbot-bot.service не запущен или не найден")
        else:
            print("  ✓ Сервис gptbot-bot.service запущен")
            
            # Проверяем логи на наличие информации о загрузке токена
            print("\n📋 Проверка логов на наличие информации о токене:")
            stdin, stdout, stderr = ssh.exec_command(
                "journalctl -u gptbot-bot.service -n 100 --no-pager | "
                r"grep -iE 'kling.*token|kling.*access|KLING_ACCESS_KEY' | tail -5 || echo 'NO_LOGS'",
                timeout=10
            )
            logs = stdout.read().decode('utf-8').strip()
            
            if logs == "NO_LOGS" or not logs:
                print("  ⚠️ В логах не найдено информации о загрузке токена KLING API")
                print("     (Возможно, токен еще не использовался или логи не содержат этой информации)")
            else:
                print("  ✓ Найдены записи о KLING API в логах:")
                for line in logs.split('\n')[:5]:
                    if line.strip():
                        # Маскируем токен в логах
                        masked_line = line
                        # Ищем и маскируем возможные токены в логе
                        import re
                        masked_line = re.sub(r'(Bearer\s+)([A-Za-z0-9]{4})([A-Za-z0-9]+)([A-Za-z0-9]{4})', 
                                           r'\1\2***\4', masked_line)
                        print(f"    {masked_line[:100]}")
        
        # 5. Рекомендации
        print("\n💡 Рекомендации:")
        print("  1. Убедитесь, что KLING_ACCESS_KEY установлен в .env файле")
        print("  2. Проверьте, что токен не содержит лишних пробелов или кавычек")
        print("  3. После обновления .env файла обязательно перезапустите сервисы:")
        print("     systemctl restart gptbot-bot.service gptbot-api.service")
        print("  4. Проверьте логи после перезапуска:")
        print("     journalctl -u gptbot-bot.service -f")
        
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if ssh:
            ssh.close()


if __name__ == "__main__":
    main()
