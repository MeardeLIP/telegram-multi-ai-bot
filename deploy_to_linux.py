#!/usr/bin/env python3
"""
Скрипт для обновления кода на Linux сервере.
"""
import paramiko
import socket
import time
import os
from pathlib import Path

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_DIR = "/opt/gptbot"
PROJECT_DIR = Path(__file__).parent

FILES_TO_COPY = [
    "app/bot/main.py",  # КРИТИЧНО: добавлено логирование callback_query и обработчик ошибок, исправлена сигнатура error_handler
    "app/bot/handlers/start.py",  # Исправлено: фото только в cmd_start, убрано из menu_main, исправлен UnboundLocalError с _admin_flag
    "app/bot/handlers/chat.py",  # КРИТИЧНО: исправлен chat_begin - добавлен cb.answer()
    "app/bot/handlers/profile.py",  # Исправлен profile_ref
    "app/bot/handlers/admin.py",  # Исправлены все обработчики
    "app/bot/handlers/promo_admin.py",  # Исправлены все обработчики
    "app/bot/handlers/promo.py",  # Исправлен promo_begin
    "app/bot/keyboards/main.py",  # НОВОЕ: добавлена кнопка "Оживить фото" в главное меню
    "app/bot/handlers/subscribe.py",  # Исправлено: удаление фото при создании счета, добавлена ReplyKeyboard, добавлен retry механизм, уменьшен таймаут, добавлен общий таймаут операции
    "app/api/main.py",  # КРИТИЧНО: улучшена обработка ошибок в create_payment endpoint, добавлено детальное логирование прокси, добавлен endpoint /thankyou
    "app/config.py",  # НОВОЕ: добавлены настройки KLING-V2 API (kling_access_key, kling_secret_key, kling_api_id, kling_api_base_url, billing_photo_animate_cost)
    "app/services/payments.py",  # КРИТИЧНО: улучшено логирование прокси, добавлена проверка httpx-socks, детальная диагностика ошибок прокси, обработка ProxyError
    "app/services/kling.py",  # НОВЫЙ: сервис для работы с KLING-V2 API (оживление фото)
    "scripts/update_proxy_env.sh",  # КРИТИЧНО: изменен на SOCKS5 прокси для поддержки HTTPS
    "scripts/test_proxy.sh",  # НОВЫЙ: скрипт для тестирования прокси
    "scripts/diagnose_proxy.py",  # НОВЫЙ: Python скрипт для диагностики прокси
    "requirements.txt",  # КРИТИЧНО: добавлен httpx-socks для поддержки SOCKS5
    "app/bot/handlers/faceswap.py",  # Добавлена ReplyKeyboard
    "app/bot/handlers/photo.py",  # НОВОЕ: добавлены обработчики для функции "Оживить фото" (menu_animate_photo, обработчики загрузки фото/видео/описания)
    "app/bot/handlers/audio.py",  # Добавлена ReplyKeyboard
    "app/bot/handlers/create_photo.py",  # Исправлено: используется safe_edit_text вместо edit_text, добавлена ReplyKeyboard
    "app/bot/utils/tg.py",  # КРИТИЧНО: исправлена функция safe_edit_text для работы с фото, добавлена обработка "message to edit not found"
    "app/bot/utils/reply_kb.py",  # НОВЫЙ: утилита для отправки ReplyKeyboard с автоматическим удалением сообщения
    "app/bot/handlers/referral.py",
    "app/bot/handlers/dialogs.py",  # Добавлена ReplyKeyboard
    "app/bot/keyboards/subscribe.py",
    "app/bot/keyboards/create_photo.py",
    "app/bot/keyboards/audio.py",
    "app/bot/keyboards/photo.py",  # НОВОЕ: добавлены клавиатуры для оживления фото (photo_animate_mode_kb, photo_animate_result_kb)
    "app/bot/keyboards/dialogs.py",
    "app/bot/keyboards/profile.py",
    "app/bot/handlers/vision.py",
    "app/bot/keyboards/faceswap.py",
    "app/bot/keyboards/chat.py",
    "app/bot/keyboards/help.py",
    "app/bot/keyboards/admin.py",
    "app/bot/keyboards/promo_admin.py",
    "app/bot/utils/notifications.py",
    "app/bot/utils/auth.py",
    "app/bot/__init__.py",
    "app/utils/openai_client.py",  # НОВЫЙ: утилита для создания OpenAI клиента с поддержкой прокси
    "app/services/image_generation.py",  # Обновлено: добавлена функция create_edit_prompt для режима редактирования фото
    "photo_2025-12-03_02-41-09.jpg",
    # Скрипты для переноса на новый сервер
    "scripts/setup_new_server.sh",  # НОВЫЙ: скрипт для первоначальной настройки сервера
    "scripts/migrate_to_new_server.sh",  # НОВЫЙ: скрипт для переноса базы данных
    # Скрипт обновления прокси в .env
    "scripts/update_proxy_env.sh",
    # Скрипт проверки синтаксиса бота
    "scripts/check_bot_syntax.sh",
    # Скрипт поиска синтаксической ошибки
    "scripts/find_syntax_error.sh",
]

# Важно: файл фото должен быть в корне проекта на сервере

def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
    """
    Устанавливает SSH соединение с повторными попытками.
    Исправляет проблему с сокетами на Windows (WinError 10038).
    """
    ssh = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"Попытка подключения {attempt}/{max_retries}...")
            
            # Закрываем предыдущее соединение, если оно было
            if ssh:
                try:
                    ssh.close()
                except:
                    pass
            
            # Создаем новый SSH клиент для каждой попытки
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Настройки для Windows: увеличиваем таймаут и используем более надежные параметры
            ssh.connect(
                hostname,
                username=username,
                password=password,
                timeout=timeout,
                allow_agent=False,
                look_for_keys=False,
                banner_timeout=30,
                auth_timeout=30
            )
            
            # Проверяем подключение простой командой
            stdin, stdout, stderr = ssh.exec_command("echo 'test'", timeout=10)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                print("✓ Подключено успешно\n")
                return ssh
            else:
                raise paramiko.SSHException(f"Тестовая команда вернула код {exit_status}")
            
        except (socket.error, OSError) as e:
            error_msg = str(e)
            print(f"✗ Ошибка сети/сокета (попытка {attempt}/{max_retries}): {error_msg}")
            if "10038" in error_msg or "not a socket" in error_msg.lower():
                print("  → Это известная проблема Windows с сокетами. Повторяем попытку...")
            if attempt < max_retries:
                wait_time = 2 * attempt  # Увеличиваем время ожидания с каждой попыткой
                print(f"  → Ожидание {wait_time} секунд перед повторной попыткой...")
                time.sleep(wait_time)
            else:
                raise ConnectionError(f"Не удалось подключиться после {max_retries} попыток. "
                                    f"Последняя ошибка: {error_msg}")
        except paramiko.AuthenticationException as e:
            print(f"✗ Ошибка аутентификации: {e}")
            print("  → Проверьте правильность пароля")
            raise
        except paramiko.SSHException as e:
            print(f"✗ SSH ошибка (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                wait_time = 2 * attempt
                print(f"  → Ожидание {wait_time} секунд перед повторной попыткой...")
                time.sleep(wait_time)
            else:
                raise
        except Exception as e:
            print(f"✗ Неожиданная ошибка (попытка {attempt}/{max_retries}): {type(e).__name__}: {e}")
            if attempt < max_retries:
                wait_time = 2 * attempt
                print(f"  → Ожидание {wait_time} секунд перед повторной попыткой...")
                time.sleep(wait_time)
            else:
                raise
    
    raise ConnectionError("Не удалось подключиться после всех попыток")


def update_kling_env(ssh, server_dir):
    """
    Обновляет переменные окружения KLING API в .env файле на сервере.
    Добавляет переменные если их нет, обновляет если они пустые или имеют другое значение.
    """
    env_file = f"{server_dir}/.env"
    
    # Переменные для добавления/обновления
    kling_vars = {
        "KLING_ACCESS_KEY": "ABpL9fYygy88pBadmD38apHCNPKNA9Yb",
        "KLING_SECRET_KEY": "EknmN4ydCgHy4nry4HhKammT9YYMQAmP",
        "KLING_API_ID": "55069011",
        "KLING_API_BASE_URL": "https://api-singapore.klingai.com/v1",
        "BILLING_PHOTO_ANIMATE_COST": "10"
    }
    
    print("\n🔧 Обновление переменных окружения KLING API...")
    
    # Проверяем существование файла
    stdin, stdout, stderr = ssh.exec_command(f"test -f {env_file} && echo 'exists' || echo 'not_exists'")
    file_exists = stdout.read().decode("utf-8").strip() == "exists"
    
    if not file_exists:
        print(f"  ⚠ Файл {env_file} не найден, создаем новый...")
        ssh.exec_command(f"touch {env_file}")
    
    # Читаем текущие значения переменных
    stdin, stdout, stderr = ssh.exec_command(f"grep -E '^({'|'.join(kling_vars.keys())})=' {env_file} 2>/dev/null || echo ''")
    existing_lines = stdout.read().decode("utf-8").strip().split('\n')
    
    existing_vars = {}
    for line in existing_lines:
        if '=' in line:
            key, value = line.split('=', 1)
            existing_vars[key.strip()] = value.strip()
    
    # Обновляем или добавляем переменные
    updated = False
    for key, value in kling_vars.items():
        if key not in existing_vars or not existing_vars[key] or existing_vars[key] != value:
            # Переменная отсутствует, пустая или имеет другое значение - обновляем
            if key in existing_vars:
                print(f"  ✓ Обновление {key}...")
                # Удаляем старую строку (экранируем специальные символы для sed)
                escaped_key = key.replace('/', '\\/').replace('.', '\\.').replace('[', '\\[').replace(']', '\\]')
                stdin, stdout, stderr = ssh.exec_command(f"sed -i '/^{escaped_key}=/d' {env_file}")
                # Ждем завершения команды
                stdout.channel.recv_exit_status()
            else:
                print(f"  ✓ Добавление {key}...")
            
            # Экранируем значение для безопасной записи в файл (заменяем одинарные кавычки)
            escaped_value = value.replace("'", "'\"'\"'")
            # Добавляем переменную в конец файла
            stdin, stdout, stderr = ssh.exec_command(f"echo '{key}={escaped_value}' >> {env_file}")
            # Ждем завершения команды
            stdout.channel.recv_exit_status()
            updated = True
        else:
            print(f"  ⊙ {key} уже установлен: {existing_vars[key][:20]}...")
    
    if updated:
        print("✅ Переменные окружения KLING API обновлены")
    else:
        print("ℹ️ Все переменные KLING API уже настроены")


def main():
    print("🚀 Обновление на Linux сервере")
    print(f"Сервер: {SERVER_USER}@{SERVER_IP}\n")
    
    password = input(f"Пароль для {SERVER_USER}@{SERVER_IP}: ")
    
    ssh = None
    try:
        ssh = connect_ssh(SERVER_IP, SERVER_USER, password)
        
        sftp = ssh.open_sftp()
        
        print("📁 Копирование файлов...")
        for file_path in FILES_TO_COPY:
            local_path = PROJECT_DIR / file_path
            if not local_path.exists():
                print(f"⚠ Пропущен (не найден): {file_path}")
                continue
            
            remote_path = f"{SERVER_DIR}/{file_path}"
            remote_dir = os.path.dirname(remote_path)
            ssh.exec_command(f"mkdir -p {remote_dir}")
            
            sftp.put(str(local_path), remote_path)
            print(f"✓ {file_path}")
        
        sftp.close()

        # Обновляем переменные окружения KLING API
        # ВАЖНО: После обновления .env файла сервисы будут перезапущены в конце скрипта
        # для загрузки новых переменных окружения
        update_kling_env(ssh, SERVER_DIR)
        
        # Проверяем, что переменные действительно обновились
        print("\n🔍 Проверка обновленных переменных KLING API в .env...")
        stdin, stdout, stderr = ssh.exec_command(
            f"grep -E '^KLING_(ACCESS_KEY|API_BASE_URL)=' {SERVER_DIR}/.env | "
            f"sed 's/ACCESS_KEY=.*/ACCESS_KEY=***/' | head -2"
        )
        env_check = stdout.read().decode("utf-8").strip()
        if env_check:
            print(env_check)
        else:
            print("⚠️ Переменные KLING API не найдены в .env файле")

        print("\n🔍 Поиск файла с синтаксической ошибкой...")
        ssh.exec_command(f"chmod +x {SERVER_DIR}/scripts/find_syntax_error.sh")
        stdin, stdout, stderr = ssh.exec_command(f"bash {SERVER_DIR}/scripts/find_syntax_error.sh")
        syntax_output = stdout.read().decode("utf-8")
        syntax_error = stderr.read().decode("utf-8")
        if syntax_output:
            print(syntax_output)
        if syntax_error:
            print("Ошибки синтаксиса:")
            print(syntax_error)
            print("\n⚠ ВНИМАНИЕ: Обнаружены ошибки синтаксиса! Бот не запустится.")
            print("⚠ Нужно исправить файл с ошибкой перед перезапуском.")
        
        # На русском сервере прокси для YooKassa не требуется
        print("\n🔍 Проверка настроек прокси в .env...")
        stdin, stdout, stderr = ssh.exec_command(f"grep -E '^(YOOKASSA_PROXY|OPENAI_PROXY)=' {SERVER_DIR}/.env || echo '⚠ Прокси не настроены в .env'")
        proxy_check = stdout.read().decode("utf-8")
        if proxy_check:
            print(proxy_check.strip())
        print("ℹ️ На русском сервере прокси для YooKassa не требуется (прямой доступ к API)")
        
        # Устанавливаем зависимости из requirements.txt (включая httpx-socks для SOCKS5)
        print("\n📦 Установка зависимостей из requirements.txt...")
        install_cmd = (
            f"cd {SERVER_DIR} && "
            f"source venv/bin/activate && "
            f"pip install -r requirements.txt --upgrade 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(install_cmd)
        # Ждем завершения команды
        exit_status = stdout.channel.recv_exit_status()
        deps_output = stdout.read().decode("utf-8")
        deps_error = stderr.read().decode("utf-8")
        
        if exit_status == 0:
            print("✅ Зависимости установлены успешно")
            # Показываем установленные пакеты
            if deps_output:
                important_lines = [line for line in deps_output.split('\n') 
                                if ('installed' in line.lower() or 'upgraded' in line.lower() 
                                or 'httpx-socks' in line.lower() or 'successfully' in line.lower())
                                and line.strip()]
                if important_lines:
                    for line in important_lines[:10]:  # Показываем первые 10 строк
                        print(f"   {line}")
        else:
            print(f"❌ Ошибка при установке зависимостей (код: {exit_status})")
            print("   Показываю вывод установки для диагностики:")
            if deps_output:
                # Показываем последние строки вывода (там обычно ошибка)
                output_lines = deps_output.strip().split('\n')
                print("   " + "\n   ".join(output_lines[-20:]))  # Последние 20 строк
            if deps_error:
                print(f"   Ошибки stderr: {deps_error[-500:]}")
            print("   Продолжаем с ручной установкой httpx-socks...")
        
        # Проверяем, что httpx-socks установлен
        print("\n🔍 Проверка установки httpx-socks...")
        check_cmd = (
            f"cd {SERVER_DIR} && "
            f"source venv/bin/activate && "
            f"python -c 'import httpx_socks; print(\"✅ httpx-socks установлен:\", httpx_socks.__version__)' 2>&1"
        )
        stdin, stdout, stderr = ssh.exec_command(check_cmd)
        check_exit = stdout.channel.recv_exit_status()
        socks_check = stdout.read().decode("utf-8")
        socks_error = stderr.read().decode("utf-8")
        
        if check_exit == 0 and socks_check:
            print(socks_check.strip())
        else:
            print("❌ httpx-socks не найден, устанавливаем вручную...")
            if socks_error:
                print(f"   Ошибка проверки: {socks_error.strip()}")
            
            # Устанавливаем httpx-socks вручную
            manual_cmd = (
                f"cd {SERVER_DIR} && "
                f"source venv/bin/activate && "
                f"pip install httpx-socks==0.9.0 2>&1"
            )
            stdin, stdout, stderr = ssh.exec_command(manual_cmd)
            manual_exit = stdout.channel.recv_exit_status()
            manual_output = stdout.read().decode("utf-8")
            manual_error = stderr.read().decode("utf-8")
            
            if manual_exit == 0:
                print("✅ httpx-socks установлен вручную")
                if manual_output:
                    success_lines = [line for line in manual_output.split('\n') 
                                   if 'successfully' in line.lower() or 'installed' in line.lower()]
                    if success_lines:
                        print(f"   {success_lines[0]}")
            else:
                print(f"❌ Ошибка установки httpx-socks (код: {manual_exit})")
                if manual_output:
                    print(f"   Вывод: {manual_output[-500:]}")
                if manual_error:
                    print(f"   Ошибки: {manual_error[-500:]}")
                print("⚠️ ВНИМАНИЕ: httpx-socks не установлен! SOCKS5 прокси не будет работать!")
        
        # Перезагружаем systemd для применения изменений в .env
        print("\n🔄 Перезагрузка systemd для применения изменений...")
        stdin, stdout, stderr = ssh.exec_command("systemctl daemon-reload")
        stdout.channel.recv_exit_status()  # Ждем завершения команды
        
        # ВАЖНО: Перезапускаем сервисы для загрузки обновленных переменных окружения из .env
        # Это критично для работы KLING API, так как токены обновляются в .env файле
        print("\n🔄 Перезапуск сервисов для применения обновленных переменных окружения...")
        stdin, stdout, stderr = ssh.exec_command(
            "systemctl restart gptbot-api.service gptbot-bot.service && "
            "sleep 2 && "
            "systemctl status gptbot-api.service --no-pager -l && "
            "systemctl status gptbot-bot.service --no-pager -l"
        )
        
        output = stdout.read().decode('utf-8')
        print(output)
        
        print("\n✅ Обновление завершено!")
        
    except KeyboardInterrupt:
        print("\n✗ Прервано пользователем")
    except Exception as e:
        print(f"\n✗ Ошибка: {e}")
        import traceback
        print("\nДетали ошибки:")
        traceback.print_exc()
    finally:
        if ssh:
            try:
                ssh.close()
            except:
                pass

if __name__ == "__main__":
    main()

