@echo off
REM Скрипт для остановки всех компонентов бота

title GPT Bot - Stopper

echo ========================================
echo   Остановка всех компонентов GPT Bot
echo ========================================
echo.

echo Остановка процессов...

REM Останавливаем бота (python -m app.bot.main)
taskkill /FI "WINDOWTITLE eq GPT Bot - Telegram Bot*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *app.bot.main*" /T /F >nul 2>&1

REM Останавливаем API (uvicorn)
taskkill /FI "WINDOWTITLE eq GPT Bot - API Server*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq python.exe" /FI "COMMANDLINE eq *uvicorn*" /T /F >nul 2>&1

REM Останавливаем Redis
taskkill /FI "WINDOWTITLE eq Redis Server*" /T /F >nul 2>&1
taskkill /FI "IMAGENAME eq redis-server.exe" /T /F >nul 2>&1

echo.
echo Все компоненты остановлены.
echo.
pause

