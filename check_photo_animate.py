#!/usr/bin/env python3
"""Проверка работоспособности функции оживления фото на сервере."""
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
        
        print("🎬 Проверка функции оживления фото")
        print("="*60)
        
        # 1. Проверка наличия необходимых файлов
        print("\n📁 Проверка наличия файлов:")
        required_files = [
            "app/services/kling.py",
            "app/bot/handlers/photo.py",
            "app/bot/keyboards/photo.py",
            "app/config.py"
        ]
        for file_path in required_files:
            full_path = f"{SERVER_DIR}/{file_path}"
            stdin, stdout, stderr = ssh.exec_command(
                f"test -f {full_path} && echo 'exists' || echo 'not_found'",
                timeout=10
            )
            result = stdout.read().decode('utf-8').strip()
            if result == "exists":
                print(f"  ✓ {file_path}")
            else:
                print(f"  ✗ {file_path} - НЕ НАЙДЕН!")
        
        # 2. Проверка переменных окружения KLING API
        print("\n🔧 Проверка переменных окружения KLING API:")
        kling_vars = [
            "KLING_ACCESS_KEY",
            "KLING_SECRET_KEY",
            "KLING_API_ID",
            "KLING_API_BASE_URL",
            "BILLING_PHOTO_ANIMATE_COST"
        ]
        env_file = f"{SERVER_DIR}/.env"
        for var_name in kling_vars:
            stdin, stdout, stderr = ssh.exec_command(
                f"grep -E '^{var_name}=' {env_file} 2>/dev/null | cut -d'=' -f1 || echo 'NOT_FOUND'",
                timeout=10
            )
            result = stdout.read().decode('utf-8').strip()
            if result == var_name:
                # Получаем значение (скрываем секретные ключи)
                stdin, stdout, stderr = ssh.exec_command(
                    f"grep -E '^{var_name}=' {env_file} 2>/dev/null | cut -d'=' -f2-",
                    timeout=10
                )
                value = stdout.read().decode('utf-8').strip()
                if 'SECRET' in var_name or 'KEY' in var_name:
                    if len(value) > 20:
                        masked = value[:10] + "..." + value[-5:]
                    else:
                        masked = "***"
                    print(f"  ✓ {var_name}={masked}")
                else:
                    print(f"  ✓ {var_name}={value}")
            else:
                print(f"  ✗ {var_name} - НЕ НАЙДЕН!")
        
        # 3. Проверка синтаксиса Python файлов
        print("\n🐍 Проверка синтаксиса Python файлов:")
        python_files = [
            "app/services/kling.py",
            "app/bot/handlers/photo.py"
        ]
        for file_path in python_files:
            full_path = f"{SERVER_DIR}/{file_path}"
            stdin, stdout, stderr = ssh.exec_command(
                f"cd {SERVER_DIR} && source venv/bin/activate && python -m py_compile {full_path} 2>&1",
                timeout=10
            )
            exit_status = stdout.channel.recv_exit_status()
            error_output = stderr.read().decode('utf-8')
            if exit_status == 0 and not error_output:
                print(f"  ✓ {file_path} - синтаксис корректен")
            else:
                print(f"  ✗ {file_path} - ОШИБКА СИНТАКСИСА!")
                if error_output:
                    print(f"    {error_output[:200]}")
        
        # 4. Проверка импорта модулей
        print("\n📦 Проверка импорта модулей:")
        # Проверка импорта kling
        stdin, stdout, stderr = ssh.exec_command(
            f"cd {SERVER_DIR} && source venv/bin/activate && python -c 'from app.services.kling import animate_photo; print(\"OK\")' 2>&1",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error_output = stderr.read().decode('utf-8')
        if exit_status == 0 and "OK" in output:
            print("  ✓ app.services.kling - импорт успешен")
        else:
            print("  ✗ app.services.kling - ОШИБКА ИМПОРТА!")
            if error_output:
                print(f"    {error_output[:300]}")
        
        # Проверка импорта обработчиков
        stdin, stdout, stderr = ssh.exec_command(
            f"cd {SERVER_DIR} && source venv/bin/activate && python -c 'from app.bot.handlers.photo import PhotoAnimateStates; print(\"OK\")' 2>&1",
            timeout=10
        )
        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8')
        error_output = stderr.read().decode('utf-8')
        if exit_status == 0 and "OK" in output:
            print("  ✓ app.bot.handlers.photo - импорт успешен")
        else:
            print("  ✗ app.bot.handlers.photo - ОШИБКА ИМПОРТА!")
            if error_output:
                print(f"    {error_output[:300]}")
        
        # 5. Проверка регистрации обработчиков в main.py
        print("\n🔗 Проверка регистрации обработчиков:")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -E '(photo_router|PhotoAnimateStates|menu_animate_photo)' {SERVER_DIR}/app/bot/main.py 2>/dev/null | head -5",
            timeout=10
        )
        registration = stdout.read().decode('utf-8')
        if "photo_router" in registration or "menu_animate_photo" in registration:
            print("  ✓ Обработчики зарегистрированы в main.py")
            if registration.strip():
                for line in registration.strip().split('\n')[:3]:
                    if line.strip():
                        print(f"    {line.strip()[:80]}")
        else:
            print("  ✗ Обработчики НЕ найдены в main.py!")
        
        # 6. Проверка логов на ошибки, связанные с оживлением фото
        print("\n📋 Проверка логов на ошибки (последние 100 строк):")
        grep_cmd = (
            "journalctl -u gptbot-bot.service -n 100 --no-pager | "
            "grep -iE '(kling|animate|photo_animate|PhotoAnimateStates|menu_animate_photo)' | tail -10"
        )
        stdin, stdout, stderr = ssh.exec_command(grep_cmd, timeout=10)
        log_errors = stdout.read().decode('utf-8')
        if log_errors.strip():
            print("  Найдены записи в логах:")
            for line in log_errors.strip().split('\n'):
                if line.strip():
                    # Показываем только последние 100 символов строки
                    print(f"    {line.strip()[-100:]}")
        else:
            print("  ℹ️ Записей, связанных с оживлением фото, не найдено")
        
        # 7. Поиск ошибок в логах
        print("\n🔍 Поиск ошибок в логах (последние 200 строк):")
        error_grep_cmd = (
            "journalctl -u gptbot-bot.service -n 200 --no-pager | "
            "grep -iE '(error|exception|traceback|failed)' | "
            "grep -iE '(kling|animate|photo)' | tail -5"
        )
        stdin, stdout, stderr = ssh.exec_command(error_grep_cmd, timeout=10)
        errors = stdout.read().decode('utf-8')
        if errors.strip():
            print("  ✗ Найдены ошибки:")
            for line in errors.strip().split('\n'):
                if line.strip():
                    print(f"    {line.strip()[-150:]}")
        else:
            print("  ✓ Ошибок, связанных с оживлением фото, не найдено")
        
        # 8. Проверка статуса сервисов
        print("\n📊 Статус сервисов:")
        stdin, stdout, stderr = ssh.exec_command(
            'systemctl status gptbot-bot.service --no-pager | grep -E "(Active:|Main PID:)"',
            timeout=10
        )
        bot_status = stdout.read().decode('utf-8')
        if bot_status.strip():
            print(f"  {bot_status.strip()}")
        
        # 9. Поиск последних task_id из логов и проверка их статуса
        print("\n🔍 Поиск последних task_id из логов KLING API:")
        task_id_cmd = (
            "journalctl -u gptbot-bot.service -n 500 --no-pager | "
            "grep -iE 'task_id|Задача создана' | "
            "grep -oE 'task_id[:\" ]+[a-zA-Z0-9_-]+' | "
            "sed 's/task_id[:\" ]*//' | "
            "sort -u | tail -5"
        )
        stdin, stdout, stderr = ssh.exec_command(task_id_cmd, timeout=15)
        task_ids = stdout.read().decode('utf-8').strip()
        
        if task_ids:
            print("  Найдены task_id:")
            for task_id in task_ids.split('\n'):
                if task_id.strip():
                    print(f"    • {task_id.strip()}")
                    # Проверяем статус задачи через API (если есть доступ к API ключам)
                    # Это можно сделать через Python скрипт на сервере
            print("  ℹ️ Для проверки статуса задач используйте API KLING напрямую")
        else:
            print("  ℹ️ task_id в логах не найдены (возможно, не было запросов)")
        
        # 10. Проверка последних запросов к KLING API
        print("\n📡 Анализ последних запросов к KLING API:")
        kling_requests_cmd = (
            "journalctl -u gptbot-bot.service -n 200 --no-pager | "
            "grep -iE '(KLING|kling|animate_photo)' | "
            "grep -E '(Начало оживления|Задача создана|Статус задачи|Видео готово|Ошибка)' | "
            "tail -10"
        )
        stdin, stdout, stderr = ssh.exec_command(kling_requests_cmd, timeout=15)
        kling_logs = stdout.read().decode('utf-8')
        if kling_logs.strip():
            print("  Последние записи о работе с KLING API:")
            for line in kling_logs.strip().split('\n'):
                if line.strip():
                    # Показываем только последние 120 символов для читаемости
                    print(f"    {line.strip()[-120:]}")
        else:
            print("  ℹ️ Записей о работе с KLING API не найдено")
        
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
