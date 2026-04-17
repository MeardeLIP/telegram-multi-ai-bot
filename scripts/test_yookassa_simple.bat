@echo off
REM Упрощенный скрипт для тестирования подключения к YooKassa API
REM Использует Python для проверки TCP соединения

title GPT Bot - Тест подключения к YooKassa (Python)

REM Получаем путь к директории, где находится этот скрипт
set SCRIPT_DIR=%~dp0

echo ========================================
echo   Тест подключения к YooKassa API
echo ========================================
echo.

echo [1/3] Проверка DNS резолюции...
echo.
nslookup api.yookassa.ru
echo.

echo [2/3] Проверка TCP соединения через Python...
echo.
REM Переходим в директорию проекта (на уровень выше scripts)
cd /d "%SCRIPT_DIR%.."
python "%SCRIPT_DIR%test_yookassa_tcp.py"
echo.

echo [3/3] Проверка доступности через диагностический endpoint...
echo.
echo Если API сервер запущен, откройте в браузере:
echo   http://localhost:8000/api/diagnostic/yookassa
echo.
echo Или используйте curl:
echo   curl http://localhost:8000/api/diagnostic/yookassa
echo.

echo ========================================
echo   Тест завершен
echo ========================================
echo.
echo Если TCP соединение не устанавливается, проблема может быть в:
echo   1. Файрволе Windows (запустите fix_yookassa_firewall.bat от имени администратора)
echo   2. Блокировке провайдера/хостинга (обратитесь к провайдеру)
echo   3. Сетевых настройках сервера
echo.
pause

