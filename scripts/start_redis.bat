@echo off
REM Скрипт для запуска Redis сервера
REM Проверяет, запущен ли Redis, и запускает его если нет

title Redis Server

REM Проверяем, запущен ли Redis на порту 6379
netstat -an | findstr ":6379" >nul 2>&1
if %errorlevel% == 0 (
    echo Redis уже запущен на порту 6379
    echo Окно можно закрыть.
    timeout /t 3 /nobreak >nul
    exit /b 0
)

echo Проверка установки Redis...
echo.

REM Проверяем, установлена ли Redis как служба Windows
sc query Redis >nul 2>&1
if %errorlevel% == 0 (
    REM Служба установлена, проверяем статус
    sc query Redis | findstr "RUNNING" >nul 2>&1
    if %errorlevel% == 0 (
        echo Redis запущен как служба Windows
        echo Окно можно закрыть.
        timeout /t 3 /nobreak >nul
        exit /b 0
    ) else (
        REM Служба установлена, но не запущена - пытаемся запустить
        echo Redis установлен как служба Windows, но не запущен.
        echo Попытка запуска службы...
        sc start Redis >nul 2>&1
        if %errorlevel% == 0 (
            echo Redis служба успешно запущена!
            timeout /t 2 /nobreak >nul
            exit /b 0
        ) else (
            echo Не удалось запустить службу Redis автоматически.
            echo Попробуйте запустить вручную: sc start Redis
            echo Или запустите Redis вручную из этой папки.
            echo.
        )
    )
)

REM Запускаем Redis
REM ВАЖНО: Укажите правильный путь к redis-server.exe
REM Если Redis установлен в другом месте, измените путь ниже:

set REDIS_FOUND=0

REM Проверяем стандартные пути установки Redis
if exist "C:\Program Files\Redis\redis-server.exe" (
    echo Найден Redis: C:\Program Files\Redis\redis-server.exe
    echo Запуск Redis...
    echo.
    cd /d "C:\Program Files\Redis"
    REM Пробуем запустить с конфигурационным файлом, если он есть
    if exist "C:\Program Files\Redis\redis.windows.conf" (
        "C:\Program Files\Redis\redis-server.exe" "C:\Program Files\Redis\redis.windows.conf"
    ) else (
        "C:\Program Files\Redis\redis-server.exe"
    )
    set REDIS_FOUND=1
) else if exist "C:\redis\redis-server.exe" (
    echo Найден Redis: C:\redis\redis-server.exe
    echo Запуск Redis...
    echo.
    "C:\redis\redis-server.exe"
    set REDIS_FOUND=1
) else if exist "C:\Program Files (x86)\Redis\redis-server.exe" (
    echo Найден Redis: C:\Program Files (x86)\Redis\redis-server.exe
    echo Запуск Redis...
    echo.
    "C:\Program Files (x86)\Redis\redis-server.exe"
    set REDIS_FOUND=1
) else (
    REM Проверяем, есть ли Redis в PATH
    where redis-server.exe >nul 2>&1
    if %errorlevel% == 0 (
        echo Найден Redis в PATH
        echo Запуск Redis...
        echo.
        redis-server.exe
        set REDIS_FOUND=1
    )
)

if %REDIS_FOUND% == 0 (
    echo.
    echo ========================================
    echo   ОШИБКА: Redis не найден!
    echo ========================================
    echo.
    echo Проверенные пути:
    echo   - C:\Program Files\Redis\redis-server.exe
    echo   - C:\redis\redis-server.exe
    echo   - C:\Program Files (x86)\Redis\redis-server.exe
    echo   - Redis в PATH системы
    echo.
    echo РЕШЕНИЕ:
    echo 1. Установите Redis для Windows
    echo    Скачать: https://github.com/microsoftarchive/redis/releases
    echo.
    echo 2. Или укажите правильный путь в файле:
    echo    scripts\start_redis.bat
    echo.
    echo 3. Или установите Redis как службу Windows:
    echo    redis-server --service-install
    echo    redis-server --service-start
    echo.
    echo 4. Или используйте Docker для Redis (если установлен Docker)
    echo.
    echo Примечание: Если Redis уже запущен как служба Windows,
    echo то этот скрипт не нужен - Redis работает автоматически.
    echo.
    pause
    exit /b 1
)

