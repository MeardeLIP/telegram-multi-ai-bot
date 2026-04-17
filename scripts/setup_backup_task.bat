@echo off
REM Скрипт для автоматической настройки задачи ежедневного бэкапа через Task Scheduler
REM Требует прав администратора

title GPT Bot - Настройка задачи бэкапа

echo ========================================
echo   Настройка ежедневного бэкапа БД
echo ========================================
echo.

REM Проверяем права администратора
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Этот скрипт требует прав администратора!
    echo Запустите его от имени администратора (правой кнопкой мыши -^> "Запуск от имени администратора")
    pause
    exit /b 1
)

REM Получаем путь к директории скриптов
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..

REM Проверяем существование файла backup_db.bat
if not exist "%SCRIPT_DIR%backup_db.bat" (
    echo ОШИБКА: Файл backup_db.bat не найден!
    echo Убедитесь, что скрипт находится в папке scripts/
    pause
    exit /b 1
)

echo [1/2] Удаление старой задачи (если существует)...
schtasks /delete /tn "GPT Bot - Daily Backup" /f >nul 2>&1

echo [2/2] Создание новой задачи ежедневного бэкапа...
REM Создаем задачу на ежедневный запуск в 3:00 ночи
schtasks /create /tn "GPT Bot - Daily Backup" /tr "\"%SCRIPT_DIR%backup_db.bat\"" /sc daily /st 03:00 /rl highest /f

if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при создании задачи!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Задача бэкапа успешно настроена!
echo ========================================
echo.
echo Задача создана в Планировщике заданий Windows.
echo Бэкап будет создаваться ежедневно в 3:00 ночи.
echo.
echo Для проверки:
echo 1. Откройте Планировщик заданий (taskschd.msc)
echo 2. Найдите задачу "GPT Bot - Daily Backup"
echo 3. Или запустите вручную: schtasks /run /tn "GPT Bot - Daily Backup"
echo.
echo Для удаления задачи используйте:
echo   schtasks /delete /tn "GPT Bot - Daily Backup" /f
echo.
pause

