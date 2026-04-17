@echo off
REM Скрипт для настройки файрвола Windows для доступа к YooKassa API
REM Требует прав администратора

title GPT Bot - Настройка файрвола для YooKassa

echo ========================================
echo   Настройка файрвола для YooKassa API
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

echo Проверка текущих правил файрвола...
echo.

REM IP адреса YooKassa API (из nslookup)
set YOOKASSA_IP1=109.235.165.99
set YOOKASSA_IP2=185.71.78.133
set YOOKASSA_PORT=443
set RULE_NAME="GPT Bot - YooKassa API Access"

echo [1/4] Удаление старых правил (если существуют)...
netsh advfirewall firewall delete rule name=%RULE_NAME% >nul 2>&1

echo [2/4] Создание правила для первого IP адреса (%YOOKASSA_IP1%)...
netsh advfirewall firewall add rule name=%RULE_NAME% dir=out action=allow protocol=TCP remoteip=%YOOKASSA_IP1% remoteport=%YOOKASSA_PORT% enable=yes

if %errorlevel% neq 0 (
    echo ОШИБКА при создании правила для %YOOKASSA_IP1%!
    pause
    exit /b 1
)

echo [3/4] Создание правила для второго IP адреса (%YOOKASSA_IP2%)...
netsh advfirewall firewall add rule name=%RULE_NAME% dir=out action=allow protocol=TCP remoteip=%YOOKASSA_IP2% remoteport=%YOOKASSA_PORT% enable=yes

if %errorlevel% neq 0 (
    echo ОШИБКА при создании правила для %YOOKASSA_IP2%!
    pause
    exit /b 1
)

echo [4/4] Проверка созданных правил...
netsh advfirewall firewall show rule name=%RULE_NAME%

echo.
echo ========================================
echo   Настройка файрвола завершена!
echo ========================================
echo.
echo Созданы правила для доступа к YooKassa API:
echo   - IP: %YOOKASSA_IP1%:%YOOKASSA_PORT%
echo   - IP: %YOOKASSA_IP2%:%YOOKASSA_PORT%
echo.
echo Теперь попробуйте снова создать платеж.
echo.
pause

