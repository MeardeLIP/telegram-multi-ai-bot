"""
Скрипт для создания бэкапа базы данных PostgreSQL.
Использует pg_dump для создания SQL дампа.
"""
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
import re

# Добавляем корневую директорию проекта в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.config import get_settings


def parse_database_url(database_url: str) -> dict:
	"""
	Парсит DATABASE_URL и извлекает параметры подключения.
	
	Формат: postgresql+psycopg://user:password@host:port/database
	"""
	# Убираем префикс postgresql+psycopg:// или postgresql://
	url = database_url.replace("postgresql+psycopg://", "").replace("postgresql://", "")
	
	# Парсим URL
	parsed = urlparse(f"postgresql://{url}")
	
	return {
		"host": parsed.hostname or "localhost",
		"port": parsed.port or 5432,
		"user": parsed.username or "app",
		"password": parsed.password or "",
		"database": parsed.path.lstrip("/") or "app",
	}


def create_backup(backup_dir: Path, db_params: dict) -> Path:
	"""
	Создает бэкап базы данных используя pg_dump.
	
	Returns:
		Path к созданному файлу бэкапа
	"""
	# Создаем имя файла с датой и временем
	timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
	backup_filename = f"backup_{timestamp}.sql"
	backup_path = backup_dir / backup_filename
	
	# Формируем команду pg_dump
	# Используем переменные окружения для пароля (безопаснее)
	env = os.environ.copy()
	env["PGPASSWORD"] = db_params["password"]
	
	cmd = [
		"pg_dump",
		"-h", db_params["host"],
		"-p", str(db_params["port"]),
		"-U", db_params["user"],
		"-d", db_params["database"],
		"-F", "p",  # plain text format
		"-f", str(backup_path),
		"--no-owner",  # Не включать команды OWNER
		"--no-acl",  # Не включать команды ACL
	]
	
	print(f"Создание бэкапа базы данных...")
	print(f"Хост: {db_params['host']}:{db_params['port']}")
	print(f"База данных: {db_params['database']}")
	print(f"Файл бэкапа: {backup_path}")
	
	try:
		result = subprocess.run(
			cmd,
			env=env,
			capture_output=True,
			text=True,
			check=True,
		)
		print(f"✅ Бэкап успешно создан: {backup_path}")
		return backup_path
	except subprocess.CalledProcessError as e:
		print(f"❌ Ошибка при создании бэкапа:")
		print(f"   {e.stderr}")
		sys.exit(1)
	except FileNotFoundError:
		print("❌ Ошибка: pg_dump не найден!")
		print("   Убедитесь, что PostgreSQL клиент установлен и доступен в PATH.")
		sys.exit(1)


def cleanup_old_backups(backup_dir: Path, keep_days: int = 30) -> None:
	"""
	Удаляет бэкапы старше указанного количества дней.
	
	Args:
		backup_dir: Директория с бэкапами
		keep_days: Количество дней для хранения бэкапов (по умолчанию 30)
	"""
	now = datetime.now()
	cutoff_date = now.timestamp() - (keep_days * 24 * 60 * 60)
	
	deleted_count = 0
	for backup_file in backup_dir.glob("backup_*.sql"):
		if backup_file.stat().st_mtime < cutoff_date:
			try:
				backup_file.unlink()
				deleted_count += 1
				print(f"🗑️  Удален старый бэкап: {backup_file.name}")
			except Exception as e:
				print(f"⚠️  Не удалось удалить {backup_file.name}: {e}")
	
	if deleted_count > 0:
		print(f"✅ Удалено старых бэкапов: {deleted_count}")


def main():
	"""Основная функция скрипта."""
	# Получаем настройки
	settings = get_settings()
	database_url = settings.database_url
	
	if not database_url:
		print("❌ Ошибка: DATABASE_URL не указан в .env файле")
		sys.exit(1)
	
	# Парсим параметры подключения
	db_params = parse_database_url(database_url)
	
	# Создаем директорию для бэкапов
	backup_dir = project_root / "backups"
	backup_dir.mkdir(exist_ok=True)
	
	# Создаем бэкап
	backup_path = create_backup(backup_dir, db_params)
	
	# Удаляем старые бэкапы (старше 30 дней)
	cleanup_old_backups(backup_dir, keep_days=30)
	
	# Показываем размер файла
	file_size_mb = backup_path.stat().st_size / (1024 * 1024)
	print(f"📊 Размер бэкапа: {file_size_mb:.2f} MB")
	
	print("\n✅ Бэкап завершен успешно!")


if __name__ == "__main__":
	main()

