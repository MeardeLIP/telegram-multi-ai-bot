#!/usr/bin/env python3
"""Проверка логов на сервере для диагностики проблемы с кнопками."""
import os
import paramiko

SERVER_IP = "149.33.0.41"
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
        print("✓ Подключено\n")

        # Проверяем статус сервисов бота и API
        print("📊 Статус сервисов (bot/api):")
        for unit in ("gptbot-bot.service", "gptbot-api.service"):
            print(f"\n=== {unit} ===")
            stdin, stdout, stderr = ssh.exec_command(
                f"systemctl status {unit} --no-pager -l -n 20"
            )
            print(stdout.read().decode("utf-8"))

        # Логи бота
        print("\n📋 Последние логи бота (50 строк):")
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-bot.service -n 50 --no-pager"
        )
        print(stdout.read().decode("utf-8"))

        # Логи API (для диагностики /payments/create)
        print("\n📋 Последние логи API (50 строк):")
        stdin, stdout, stderr = ssh.exec_command(
            "journalctl -u gptbot-api.service -n 50 --no-pager"
        )
        print(stdout.read().decode("utf-8"))

        # Поиск ошибок в логах бота и API
        print("\n🔍 Поиск ошибок в логах (bot/api):")
        grep_cmd = (
            "journalctl -u gptbot-bot.service -u gptbot-api.service "
            "-n 200 --no-pager | grep -i 'error\\|exception\\|traceback\\|timeout'"
        )
        stdin, stdout, stderr = ssh.exec_command(grep_cmd)
        print(stdout.read().decode("utf-8"))

        # Быстрая проверка доступности API и эндпоинта /payments/create
        print("\n🌐 Проверка доступности API (health и payments/create):")
        health_cmd = (
            "curl -sS -o /dev/null -w '  /health -> HTTP %{http_code}, time %{time_total}s\\n' "
            "http://149.33.0.41:8000/health || echo '  /health -> ERROR'"
        )
        payments_cmd = (
            "curl -sS -o /dev/null -w '  /payments/create -> HTTP %{http_code}, time %{time_total}s\\n' "
            "-H 'Content-Type: application/json' "
            "-X POST "
            "-d '{\"plan_code\":\"P1D_50K\",\"user_id\":356142844}' "
            "http://149.33.0.41:8000/payments/create || echo '  /payments/create -> ERROR'"
        )
        for cmd in (health_cmd, payments_cmd):
            stdin, stdout, stderr = ssh.exec_command(cmd)
            print(stdout.read().decode("utf-8"))

    except Exception as e:
        print(f"✗ Ошибка: {e}")
    finally:
        ssh.close()


if __name__ == "__main__":
    main()

