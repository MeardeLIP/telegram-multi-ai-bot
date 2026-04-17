#!/usr/bin/env python3
"""
Скрипт для изменения ADMIN_IDS в .env файле на сервере.
"""
import paramiko
import re
from datetime import datetime

SERVER_IP = "93.88.203.86"
SERVER_USER = "root"
SERVER_PASSWORD = "n5nxGTZeFztJf"
SERVER_DIR = "/opt/gptbot"
ENV_FILE = f"{SERVER_DIR}/.env"

OLD_ADMIN_ID = "1177786625"
NEW_ADMIN_ID = "356142844"


def connect_ssh(hostname, username, password, max_retries=3, timeout=30):
	"""Устанавливает SSH соединение."""
	ssh = None
	for attempt in range(1, max_retries + 1):
		try:
			if ssh:
				try:
					ssh.close()
				except:
					pass
			
			ssh = paramiko.SSHClient()
			ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
			ssh.connect(
				hostname, username=username, password=password,
				timeout=timeout, allow_agent=False, look_for_keys=False,
				banner_timeout=30, auth_timeout=30
			)
			
			stdin, stdout, stderr = ssh.exec_command("echo 'test'", timeout=10)
			exit_status = stdout.channel.recv_exit_status()
			if exit_status == 0:
				return ssh
		except Exception as e:
			if attempt < max_retries:
				import time
				time.sleep(2 * attempt)
			else:
				raise
	raise ConnectionError("Не удалось подключиться")


def main():
	ssh = None
	try:
		print("🔧 Изменение ADMIN_IDS в .env файле на сервере")
		print("=" * 60)
		
		# Подключаемся к серверу
		print(f"\n📡 Подключение к серверу {SERVER_IP}...")
		ssh = connect_ssh(SERVER_IP, SERVER_USER, SERVER_PASSWORD)
		print("✅ Подключение установлено")
		
		# Создаем резервную копию .env файла
		print(f"\n💾 Создание резервной копии .env файла...")
		backup_name = f".env.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
		backup_cmd = f"cd {SERVER_DIR} && cp .env {backup_name}"
		stdin, stdout, stderr = ssh.exec_command(backup_cmd, timeout=10)
		exit_status = stdout.channel.recv_exit_status()
		if exit_status == 0:
			print(f"✅ Резервная копия создана: {backup_name}")
		else:
			error = stderr.read().decode('utf-8')
			print(f"⚠️ Предупреждение при создании бэкапа: {error}")
		
		# Читаем .env файл
		print(f"\n📖 Чтение .env файла...")
		read_cmd = f"cat {ENV_FILE}"
		stdin, stdout, stderr = ssh.exec_command(read_cmd, timeout=10)
		exit_status = stdout.channel.recv_exit_status()
		if exit_status != 0:
			error = stderr.read().decode('utf-8')
			raise Exception(f"Не удалось прочитать .env файл: {error}")
		
		env_content = stdout.read().decode('utf-8')
		print(f"✅ .env файл прочитан ({len(env_content)} символов)")
		
		# Проверяем текущее значение ADMIN_IDS
		old_pattern = re.compile(rf'ADMIN_IDS\s*=\s*.*{re.escape(OLD_ADMIN_ID)}.*', re.IGNORECASE)
		if not old_pattern.search(env_content):
			print(f"\n⚠️ ВНИМАНИЕ: ADMIN_IDS со значением {OLD_ADMIN_ID} не найден в .env файле!")
			print("Текущее содержимое ADMIN_IDS:")
			admin_ids_lines = [line for line in env_content.split('\n') if 'ADMIN_IDS' in line.upper()]
			for line in admin_ids_lines:
				print(f"  {line}")
			
			response = input(f"\nПродолжить замену? (y/n): ")
			if response.lower() != 'y':
				print("❌ Операция отменена")
				return
		
		# Заменяем значение ADMIN_IDS
		print(f"\n🔄 Замена ADMIN_IDS: {OLD_ADMIN_ID} -> {NEW_ADMIN_ID}...")
		
		# Паттерны для замены (разные форматы)
		patterns = [
			# ADMIN_IDS=356142844
			(rf'ADMIN_IDS\s*=\s*{re.escape(OLD_ADMIN_ID)}\s*$', f'ADMIN_IDS={NEW_ADMIN_ID}'),
			# ADMIN_IDS=356142844,123456789
			(rf'ADMIN_IDS\s*=\s*{re.escape(OLD_ADMIN_ID)}\s*,', f'ADMIN_IDS={NEW_ADMIN_ID},'),
			# ADMIN_IDS=123456789,356142844
			(rf'ADMIN_IDS\s*=\s*([^,\s]+,\s*)?{re.escape(OLD_ADMIN_ID)}(\s*,\s*[^,\s]+)?\s*$', f'ADMIN_IDS={NEW_ADMIN_ID}'),
			# ADMIN_IDS="356142844"
			(rf'ADMIN_IDS\s*=\s*["\']?{re.escape(OLD_ADMIN_ID)}["\']?\s*$', f'ADMIN_IDS={NEW_ADMIN_ID}'),
		]
		
		modified = False
		for pattern, replacement in patterns:
			if re.search(pattern, env_content, re.IGNORECASE | re.MULTILINE):
				env_content = re.sub(pattern, replacement, env_content, flags=re.IGNORECASE | re.MULTILINE)
				modified = True
				break
		
		if not modified:
			# Если не нашли точное совпадение, попробуем более общий подход
			# Заменяем любое вхождение OLD_ADMIN_ID на NEW_ADMIN_ID в строке с ADMIN_IDS
			lines = env_content.split('\n')
			for i, line in enumerate(lines):
				if 'ADMIN_IDS' in line.upper() and OLD_ADMIN_ID in line:
					lines[i] = re.sub(
						rf'\b{re.escape(OLD_ADMIN_ID)}\b',
						NEW_ADMIN_ID,
						line,
						flags=re.IGNORECASE
					)
					modified = True
			env_content = '\n'.join(lines)
		
		if not modified:
			raise Exception(f"Не удалось найти и заменить ADMIN_IDS={OLD_ADMIN_ID} в .env файле")
		
		print(f"✅ Значение заменено в памяти")
		
		# Сохраняем измененный .env файл
		print(f"\n💾 Сохранение изменений в .env файл...")
		sftp = ssh.open_sftp()
		try:
			with sftp.file(ENV_FILE, 'w') as f:
				f.write(env_content)
			print("✅ Изменения сохранены")
		finally:
			sftp.close()
		
		# Проверяем изменение
		print(f"\n🔍 Проверка изменений...")
		check_cmd = f"grep ADMIN_IDS {ENV_FILE}"
		stdin, stdout, stderr = ssh.exec_command(check_cmd, timeout=10)
		exit_status = stdout.channel.recv_exit_status()
		if exit_status == 0:
			result = stdout.read().decode('utf-8').strip()
			print(f"Текущее значение ADMIN_IDS:")
			for line in result.split('\n'):
				print(f"  {line}")
			
			if NEW_ADMIN_ID in result:
				print("✅ Изменение подтверждено")
			else:
				print("⚠️ ВНИМАНИЕ: Новое значение не найдено в файле!")
		else:
			print("⚠️ Не удалось проверить изменения")
		
		# Перезапускаем сервисы
		print(f"\n🔄 Перезапуск сервисов бота...")
		restart_commands = [
			"systemctl restart gptbot-api.service",
			"systemctl restart gptbot-bot.service"
		]
		
		for cmd in restart_commands:
			stdin, stdout, stderr = ssh.exec_command(cmd, timeout=30)
			exit_status = stdout.channel.recv_exit_status()
			if exit_status == 0:
				print(f"✅ {cmd} - выполнено")
			else:
				error = stderr.read().decode('utf-8')
				print(f"⚠️ {cmd} - предупреждение: {error}")
		
		# Проверяем статус сервисов
		print(f"\n📊 Проверка статуса сервисов...")
		status_commands = [
			"systemctl is-active gptbot-api.service",
			"systemctl is-active gptbot-bot.service"
		]
		
		for cmd in status_commands:
			stdin, stdout, stderr = ssh.exec_command(cmd, timeout=10)
			exit_status = stdout.channel.recv_exit_status()
			status = stdout.read().decode('utf-8').strip()
			service_name = cmd.split()[-1]
			if status == "active":
				print(f"✅ {service_name} - активен")
			else:
				print(f"⚠️ {service_name} - статус: {status}")
		
		print("\n" + "=" * 60)
		print("✅ Изменение ADMIN_IDS завершено успешно!")
		print(f"Старое значение: {OLD_ADMIN_ID}")
		print(f"Новое значение: {NEW_ADMIN_ID}")
		
	except Exception as e:
		print(f"\n❌ Ошибка: {e}")
		import traceback
		traceback.print_exc()
	finally:
		if ssh:
			try:
				ssh.close()
			except:
				pass


if __name__ == "__main__":
	main()
