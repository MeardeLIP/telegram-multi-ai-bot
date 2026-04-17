@echo off
REM Главный скрипт для запуска всех компонентов бота
REM Запускает Redis, API и Bot в отдельных окнах

title GPT Bot - Launcher

echo ========================================
echo   Запуск GPT Bot - Все компоненты
echo ========================================
echo.

REM Получаем путь к директории скриптов
set SCRIPT_DIR=%~dp0

REM Проверяем наличие .env файла
cd /d "%SCRIPT_DIR%.."
if not exist ".env" (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env на основе .env.example
    pause
    exit /b 1
)

echo [1/3] Запуск Redis...
start "Redis Server" "%SCRIPT_DIR%start_redis.bat"

REM Ждем 3 секунды, чтобы Redis успел запуститься
timeout /t 3 /nobreak >nul

echo [2/3] Запуск API сервера...
start "GPT Bot - API" "%SCRIPT_DIR%start_api.bat"

REM Ждем 5 секунд, чтобы API успел запуститься
timeout /t 5 /nobreak >nul

echo [3/3] Запуск Telegram бота...
start "GPT Bot - Bot" "%SCRIPT_DIR%start_bot.bat"

echo.
echo ========================================
echo   Все компоненты запущены!
echo ========================================
echo.
echo Окна компонентов открыты в отдельных окнах.
echo Закройте это окно - компоненты продолжат работать.
echo.
echo Для остановки всех компонентов:
echo 1. Закройте окна Redis, API и Bot
echo 2. Или используйте скрипт stop_all.bat
echo.
timeout /t 3 /nobreak >nul

