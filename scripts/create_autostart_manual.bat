@echo off
REM Ручное создание задачи автозапуска через командную строку
REM Этот скрипт можно запустить от имени администратора для создания задачи

title GPT Bot - Ручное создание автозапуска

echo ========================================
echo   Ручное создание автозапуска GPT Bot
echo ========================================
echo.

REM Проверяем права администратора
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ОШИБКА: Этот скрипт требует прав администратора!
    echo Запустите его от имени администратора
    pause
    exit /b 1
)

REM Получаем путь к директории скриптов
set SCRIPT_DIR=%~dp0
set START_ALL_BAT=%SCRIPT_DIR%start_all.bat

echo Текущий путь к скрипту: %START_ALL_BAT%
echo.

REM Проверяем существование файла
if not exist "%START_ALL_BAT%" (
    echo ОШИБКА: Файл start_all.bat не найден по пути:
    echo %START_ALL_BAT%
    echo.
    echo Убедитесь, что файл существует!
    pause
    exit /b 1
)

echo Файл start_all.bat найден!
echo.

REM Удаляем старую задачу, если существует
echo [1/3] Удаление старой задачи (если существует)...
schtasks /delete /tn "GPT Bot - Auto Start" /f >nul 2>&1
if %errorlevel% == 0 (
    echo Старая задача удалена.
) else (
    echo Старой задачи не было (это нормально).
)
echo.

REM Создаем новую задачу
echo [2/3] Создание новой задачи автозапуска...
echo Команда: schtasks /create /tn "GPT Bot - Auto Start" /tr "%START_ALL_BAT%" /sc onlogon /rl highest /f
echo.

schtasks /create /tn "GPT Bot - Auto Start" /tr "\"%START_ALL_BAT%\"" /sc onlogon /rl highest /f

if %errorlevel% neq 0 (
    echo.
    echo ОШИБКА при создании задачи!
    echo.
    echo Попробуйте создать задачу вручную через Планировщик заданий:
    echo 1. Откройте Планировщик заданий (taskschd.msc)
    echo 2. Создайте задачу вручную
    echo 3. Укажите путь: %START_ALL_BAT%
    pause
    exit /b 1
)

echo.
echo [3/3] Проверка созданной задачи...
schtasks /query /tn "GPT Bot - Auto Start" >nul 2>&1
if %errorlevel% == 0 (
    echo.
    echo ========================================
    echo   Задача успешно создана!
    echo ========================================
    echo.
    echo Имя задачи: GPT Bot - Auto Start
    echo Путь к скрипту: %START_ALL_BAT%
    echo Триггер: При входе в систему
    echo.
    echo Для проверки:
    echo 1. Откройте Планировщик заданий (taskschd.msc)
    echo 2. Найдите задачу "GPT Bot - Auto Start"
    echo 3. Или выполните: schtasks /query /tn "GPT Bot - Auto Start"
    echo.
    echo Для тестового запуска:
    echo   schtasks /run /tn "GPT Bot - Auto Start"
    echo.
) else (
    echo ОШИБКА: Задача не найдена после создания!
)

pause

