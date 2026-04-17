@echo off
REM Скрипт для запуска Telegram бота

title GPT Bot - Telegram Bot

REM Переходим в директорию проекта
cd /d "%~dp0.."

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env на основе .env.example
    pause
    exit /b 1
)

REM Ждем 5 секунд, чтобы API успел запуститься
timeout /t 5 /nobreak >nul

REM Запускаем бота
python -m app.bot.main

REM Если произошла ошибка, показываем сообщение
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при запуске бота!
    echo Проверьте:
    echo 1. Установлен ли Python и все зависимости (pip install -r requirements.txt)
    echo 2. Правильно ли настроен .env файл (BOT_TOKEN и другие переменные)
    echo 3. Запущен ли API сервер (http://localhost:8000)
    echo 4. Запущен ли PostgreSQL
    echo 5. Запущен ли Redis
    pause
)

