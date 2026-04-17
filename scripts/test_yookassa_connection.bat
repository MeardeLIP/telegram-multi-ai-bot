@echo off
REM Скрипт для тестирования подключения к YooKassa API
REM Проверяет DNS, TCP соединение и доступность через разные методы

title GPT Bot - Тест подключения к YooKassa

echo ========================================
echo   Тест подключения к YooKassa API
echo ========================================
echo.

echo [1/4] Проверка DNS резолюции...
echo.
nslookup api.yookassa.ru
echo.

echo [2/4] Проверка TCP соединения к первому IP (109.235.165.99:443)...
echo.
powershell -Command "Test-NetConnection -ComputerName 109.235.165.99 -Port 443 -InformationLevel Detailed"
echo.

echo [3/4] Проверка TCP соединения ко второму IP (185.71.78.133:443)...
echo.
powershell -Command "Test-NetConnection -ComputerName 185.71.78.133 -Port 443 -InformationLevel Detailed"
echo.

echo [4/4] Проверка через доменное имя (api.yookassa.ru:443)...
echo.
powershell -Command "Test-NetConnection -ComputerName api.yookassa.ru -Port 443 -InformationLevel Detailed"
echo.

echo ========================================
echo   Тест завершен
echo ========================================
echo.
echo Если все тесты показывают "TcpTestSucceeded : False",
echo то проблема может быть в:
echo   1. Файрволе Windows (запустите fix_yookassa_firewall.bat от имени администратора)
echo   2. Блокировке провайдера/хостинга (обратитесь к провайдеру)
echo   3. Сетевых настройках сервера
echo.
pause

