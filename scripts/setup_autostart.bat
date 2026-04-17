@echo off
REM Скрипт для автоматической настройки автозапуска бота через Task Scheduler
REM Требует прав администратора

title GPT Bot - Настройка автозапуска

echo ========================================
echo   Настройка автозапуска GPT Bot
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

REM Проверяем существование файла start_all.bat
if not exist "%SCRIPT_DIR%start_all.bat" (
    echo ОШИБКА: Файл start_all.bat не найден!
    echo Убедитесь, что скрипт находится в папке scripts/
    pause
    exit /b 1
)

echo [1/2] Удаление старой задачи (если существует)...
schtasks /delete /tn "GPT Bot - Auto Start" /f >nul 2>&1

echo [2/2] Создание новой задачи автозапуска...
schtasks /create /tn "GPT Bot - Auto Start" /tr "\"%SCRIPT_DIR%start_all.bat\"" /sc onlogon /rl highest /f

if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при создании задачи!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Автозапуск успешно настроен!
echo ========================================
echo.
echo Задача создана в Планировщике заданий Windows.
echo Бот будет автоматически запускаться при входе в систему.
echo.
echo Для проверки:
echo 1. Перезагрузите компьютер или выйдите из системы
echo 2. Войдите в систему снова
echo 3. Проверьте, что процессы бота запущены (Диспетчер задач)
echo.
echo Для удаления автозапуска используйте:
echo   schtasks /delete /tn "GPT Bot - Auto Start" /f
echo.
pause

