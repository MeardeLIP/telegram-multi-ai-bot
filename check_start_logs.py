#!/usr/bin/env python3
"""Проверка логов бота на сервере для диагностики проблемы с /start."""
import os
import paramiko

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_DIR = "/opt/gptbot"


def get_password() -> str:
    """
    Возвращает пароль для подключения к серверу.
    
    Важно: в автоматическом режиме пароль можно передать через
    переменную окружения GPTBOT_SERVER_PASSWORD, чтобы скрипт
    не запрашивал ввод в интерактивном режиме.
    """
    env_password = os.getenv("GPTBOT_SERVER_PASSWORD")
    if env_password:
        return env_password
    return input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")


def main() -> None:
    password = get_password()
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(SERVER_IP, username=SERVER_USER, password=password, timeout=10)
        print("✓ Подключено к серверу\n")
        
        # 1. Проверка статуса сервиса
        print("=" * 60)
        print("📊 СТАТУС СЕРВИСА GPTBOT-BOT")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl status gptbot-bot.service --no-pager -l -n 20"
        )
        status_output = stdout.read().decode('utf-8')
        print(status_output)
        
        # Проверяем, активен ли сервис
        if "Active: active (running)" in status_output:
            print("✅ Сервис активен и работает\n")
        elif "Active: inactive" in status_output or "Active: failed" in status_output:
            print("❌ ВНИМАНИЕ: Сервис не активен или упал!\n")
        else:
            print("⚠️ Не удалось определить статус сервиса\n")
        
        # 2. Поиск упоминаний /start в логах за последние 2 часа
        print("=" * 60)
        print("🔍 ПОИСК УПОМИНАНИЙ /start В ЛОГАХ (последние 2 часа)")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '2 hours ago' --no-pager | "
            "grep -iE '/start|CommandStart|🔵.*start|start received' | tail -50"
        )
        start_mentions = stdout.read().decode('utf-8')
        if start_mentions.strip():
            print(start_mentions)
            print(f"\n✅ Найдено упоминаний /start: {len(start_mentions.strip().split(chr(10)))}")
        else:
            print("❌ Упоминаний /start в логах НЕ НАЙДЕНО за последние 2 часа")
            print("   Это может означать, что:")
            print("   - Обработчик /start не вызывается")
            print("   - Сообщения не доходят до бота")
            print("   - Бот не запущен или не работает")
        
        # 3. Поиск маркера "🔵 /start received" (который мы добавили)
        print("\n" + "=" * 60)
        print("🔵 ПОИСК МАРКЕРА '🔵 /start received' (логирование начала обработки)")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '2 hours ago' --no-pager | "
            "grep -i '🔵.*start received' | tail -20"
        )
        marker_logs = stdout.read().decode('utf-8')
        if marker_logs.strip():
            print(marker_logs)
            print(f"\n✅ Обработчик /start вызывался {len(marker_logs.strip().split(chr(10)))} раз(а)")
        else:
            print("❌ Маркер '🔵 /start received' НЕ НАЙДЕН")
            print("   Это означает, что обработчик cmd_start НЕ ВЫЗЫВАЕТСЯ")
            print("   Возможные причины:")
            print("   - Обработчик не зарегистрирован")
            print("   - Другой обработчик перехватывает сообщения раньше")
            print("   - Проблема с роутингом в aiogram")
        
        # 4. Поиск ошибок, связанных с /start
        print("\n" + "=" * 60)
        print("❌ ПОИСК ОШИБОК, СВЯЗАННЫХ С /start")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '2 hours ago' --no-pager | "
            "grep -iE '❌.*start|error.*start|exception.*start|traceback.*start|failed.*start' | tail -30"
        )
        start_errors = stdout.read().decode('utf-8')
        if start_errors.strip():
            print(start_errors)
            print("\n⚠️ Найдены ошибки, связанные с /start!")
        else:
            print("✅ Ошибок, связанных с /start, не найдено")
        
        # 5. Последние логи бота (100 строк)
        print("\n" + "=" * 60)
        print("📋 ПОСЛЕДНИЕ ЛОГИ БОТА (100 строк)")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service -n 100 --no-pager"
        )
        recent_logs = stdout.read().decode('utf-8')
        print(recent_logs)
        
        # 6. Проверка регистрации обработчика (поиск упоминаний о запуске бота)
        print("\n" + "=" * 60)
        print("🚀 ПРОВЕРКА РЕГИСТРАЦИИ ОБРАБОТЧИКОВ И ЗАПУСКА БОТА")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '1 hour ago' --no-pager | "
            "grep -iE 'Starting Telegram bot|include_router|router|CommandStart|handlers' | tail -20"
        )
        registration_logs = stdout.read().decode('utf-8')
        if registration_logs.strip():
            print(registration_logs)
        else:
            print("⚠️ Не найдено логов о регистрации обработчиков")
        
        # 7. Проверка активности бота (любые входящие сообщения)
        print("\n" + "=" * 60)
        print("💬 ПРОВЕРКА АКТИВНОСТИ БОТА (входящие сообщения)")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '1 hour ago' --no-pager | "
            "grep -iE 'message|callback|update|from_user' | tail -30"
        )
        activity_logs = stdout.read().decode('utf-8')
        if activity_logs.strip():
            print(activity_logs)
            print(f"\n✅ Бот получает сообщения ({len(activity_logs.strip().split(chr(10)))} записей)")
        else:
            print("❌ НЕ НАЙДЕНО входящих сообщений за последний час")
            print("   Это может означать, что бот не получает обновления от Telegram")
        
        # 8. Проверка последних ошибок вообще
        print("\n" + "=" * 60)
        print("🔍 ПОСЛЕДНИЕ ОШИБКИ В ЛОГАХ (любые)")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service --since '2 hours ago' --no-pager | "
            "grep -iE 'error|exception|traceback|failed|❌' | tail -20"
        )
        all_errors = stdout.read().decode('utf-8')
        if all_errors.strip():
            print(all_errors)
        else:
            print("✅ Критических ошибок не найдено")
        
        # 9. Проверка времени последнего логирования
        print("\n" + "=" * 60)
        print("⏰ ВРЕМЯ ПОСЛЕДНЕГО ЛОГИРОВАНИЯ")
        print("=" * 60)
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service -n 1 --no-pager --format='%Y-%m-%d %H:%M:%S %s'"
        )
        last_log_time = stdout.read().decode('utf-8').strip()
        if last_log_time:
            print(f"Последняя запись в логе: {last_log_time}")
        else:
            print("⚠️ Не удалось определить время последнего логирования")
        
        print("\n" + "=" * 60)
        print("✅ ПРОВЕРКА ЗАВЕРШЕНА")
        print("=" * 60)
        
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ssh.close()


if __name__ == "__main__":
    main()
