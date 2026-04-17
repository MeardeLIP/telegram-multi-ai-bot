@echo off
REM Скрипт для запуска бэкапа базы данных

title GPT Bot - Database Backup

REM Переходим в директорию проекта
cd /d "%~dp0.."

REM Проверяем наличие .env файла
if not exist ".env" (
    echo ОШИБКА: Файл .env не найден!
    echo Создайте файл .env на основе .env.example
    pause
    exit /b 1
)

REM Запускаем скрипт бэкапа
python scripts\backup_db.py

REM Если произошла ошибка, показываем сообщение
if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при создании бэкапа!
    echo Проверьте:
    echo 1. Установлен ли PostgreSQL клиент (pg_dump должен быть в PATH)
    echo 2. Правильно ли настроен DATABASE_URL в .env файле
    echo 3. Доступна ли база данных
    pause
)

