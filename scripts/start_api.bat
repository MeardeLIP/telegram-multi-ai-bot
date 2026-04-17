@echo off
REM Скрипт для запуска API сервера (FastAPI/Uvicorn)

title GPT Bot - API Server

REM Переходим в директорию проекта
cd /d "%~dp0.."

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env на основе .env.example
    pause
    exit /b 1
)

REM Запускаем API сервер через run.py (устанавливает правильный event loop для Windows)
python -m app.api.run

REM Если произошла ошибка, показываем сообщение
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при запуске API сервера!
    echo Проверьте:
    echo 1. Установлен ли Python и все зависимости (pip install -r requirements.txt)
    echo 2. Правильно ли настроен .env файл
    echo 3. Запущен ли PostgreSQL
    echo 4. Запущен ли Redis
    pause
)

