"""
Точка входа для запуска API сервера.
Устанавливает WindowsSelectorEventLoopPolicy для Windows ДО создания event loop.
"""
import sys
import asyncio

# КРИТИЧЕСКИ ВАЖНО: Установить event loop policy ДО импорта uvicorn или приложения
# Это необходимо для работы psycopg (async PostgreSQL драйвер) на Windows
if sys.platform == "win32":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Теперь можно импортировать приложение
from app.api.main import app

if __name__ == "__main__":
	import uvicorn
	uvicorn.run(app, host="0.0.0.0", port=8000)

