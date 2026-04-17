import os
import subprocess
import sys
import json
import configparser
from pathlib import Path
import platform


# --- Определение системы и пакетного менеджера ---
def detect_system():
    """Определяет тип системы и возвращает соответствующий пакетный менеджер"""
    system_info = {
        'os': platform.system().lower(),
        'distro': None,
        'package_manager': None,
        'update_cmd': None,
        'install_cmd': None
    }
    
    try:
        # Определяем дистрибутив Linux
        if os.path.exists('/etc/os-release'):
            with open('/etc/os-release', 'r') as f:
                for line in f:
                    if line.startswith('ID='):
                        system_info['distro'] = line.split('=')[1].strip().strip('"')
                        break
        
        # Определяем пакетный менеджер
        if system_info['distro'] in ['ubuntu', 'debian', 'linuxmint', 'kali']:
            system_info['package_manager'] = 'apt'
            system_info['update_cmd'] = 'apt update'
            system_info['install_cmd'] = 'apt install -y'
        elif system_info['distro'] in ['fedora', 'rhel', 'centos', 'rocky', 'alma', 'amazon']:
            system_info['package_manager'] = 'dnf'
            system_info['update_cmd'] = 'dnf update -y'
            system_info['install_cmd'] = 'dnf install -y'
        elif system_info['distro'] in ['arch', 'manjaro']:
            system_info['package_manager'] = 'pacman'
            system_info['update_cmd'] = 'pacman -Sy'
            system_info['install_cmd'] = 'pacman -S --noconfirm'
        elif system_info['distro'] in ['opensuse', 'sles']:
            system_info['package_manager'] = 'zypper'
            system_info['update_cmd'] = 'zypper refresh'
            system_info['install_cmd'] = 'zypper install -y'
        else:
            # Fallback на apt для неизвестных дистрибутивов
            system_info['package_manager'] = 'apt'
            system_info['update_cmd'] = 'apt update'
            system_info['install_cmd'] = 'apt install -y'
            
    except Exception as e:
        console.print(f"[yellow]⚠️ Не удалось определить систему, использую apt по умолчанию: {e}[/yellow]")
        system_info['package_manager'] = 'apt'
        system_info['update_cmd'] = 'apt update'
        system_info['install_cmd'] = 'apt install -y'
    
    return system_info


# Глобальная переменная с информацией о системе
SYSTEM_INFO = detect_system()


# --- Установка недостающих модулей ---
def install_and_import(package):
    try:
        __import__(package)
    except ImportError:
        print(f"🔵 Устанавливаю недостающий модуль: {package}...")
        if SYSTEM_INFO['package_manager'] == 'apt':
            subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--break-system-packages"])
        elif SYSTEM_INFO['package_manager'] == 'dnf':
            subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        elif SYSTEM_INFO['package_manager'] == 'pacman':
            subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} python-pip python-virtualenv", shell=True, check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        elif SYSTEM_INFO['package_manager'] == 'zypper':
            subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        else:
            subprocess.run("apt update", shell=True, check=True)
            subprocess.run("apt install -y python3-pip python3-venv", shell=True, check=True)
            subprocess.check_call([sys.executable, "-m", "pip", "install", package, "--break-system-packages"])


# Список нужных пакетов
required_packages = [
    "rich",
]

for package in required_packages:
    install_and_import(package)

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table


class ProjectConfig:
    def __init__(self, config_file="project.conf"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.create_default_config()
    
    def create_default_config(self):
        self.config['PROJECT'] = {
            'name': 'myproject',
            'main_script': 'main.py',
            'requirements_file': 'requirements.txt',
            'venv_name': 'venv',
            'service_name': 'myproject',
            'user': 'root',
            'description': 'My Project Service'
        }
        
        self.config['NGINX'] = {
            'config_template': 'nginx.conf',
            'target_path': '/etc/nginx/nginx.conf'
        }
        
        self.config['CERTBOT'] = {
            'renew_script_path': '/root/certbot-renew.sh',
            'cron_schedule': '0 3 * * *'
        }
        
        self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)
    
    def get(self, section, key, fallback=None):
        return self.config.get(section, key, fallback=fallback)
    
    def set(self, section, key, value):
        if section not in self.config:
            self.config[section] = {}
        self.config[section][key] = value
        self.save_config()


config = ProjectConfig()
SERVICE_NAME = config.get('PROJECT', 'service_name', 'myproject')
MAIN_SCRIPT = config.get('PROJECT', 'main_script', 'main.py')
REQUIREMENTS_FILE = config.get('PROJECT', 'requirements_file', 'requirements.txt')
VENV_NAME = config.get('PROJECT', 'venv_name', 'venv')

try:
    sys.stdin.reconfigure(encoding='utf-8')
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

if not os.environ.get("LC_ALL", "").endswith("UTF-8"):
    os.environ["LC_ALL"] = "en_US.UTF-8"
    os.environ["LANG"] = "en_US.UTF-8"

console = Console()


# --- Установка зависимостей ---
def install_dependencies():
    console.print("[blue]🔧 Установка зависимостей...[/blue]")
    with console.status("[bold green]Устанавливаются зависимости...[/bold green]"):
        try:
            if not os.path.exists(VENV_NAME):
                console.print("[yellow]⚠️ Виртуальное окружение не найдено. Создаю...[/yellow]")
                subprocess.run(f"python3 -m venv {VENV_NAME}", shell=True, check=True)

            subprocess.run(f"bash -c 'source {VENV_NAME}/bin/activate && pip install -r {REQUIREMENTS_FILE}'", shell=True, check=True)

        except subprocess.CalledProcessError:
            console.print("[red]❌ Ошибка при установке зависимостей. Пробую исправить автоматически...[/red]")

            try:
                if SYSTEM_INFO['package_manager'] == 'apt':
                    subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
                    subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
                elif SYSTEM_INFO['package_manager'] == 'dnf':
                    subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
                    subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
                elif SYSTEM_INFO['package_manager'] == 'pacman':
                    subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
                    subprocess.run(f"{SYSTEM_INFO['install_cmd']} python-pip python-virtualenv", shell=True, check=True)
                elif SYSTEM_INFO['package_manager'] == 'zypper':
                    subprocess.run(SYSTEM_INFO['update_cmd'], shell=True, check=True)
                    subprocess.run(f"{SYSTEM_INFO['install_cmd']} python3-pip python3-venv", shell=True, check=True)
                else:
                    subprocess.run("apt update", shell=True, check=True)
                    subprocess.run("apt install -y python3-pip python3-venv", shell=True, check=True)
                
                console.print(f"[green]✅ Установлены необходимые пакеты через {SYSTEM_INFO['package_manager']}. Повторяю установку...[/green]")

                subprocess.run(f"python3 -m venv {VENV_NAME}", shell=True, check=True)
                subprocess.run(f"bash -c 'source {VENV_NAME}/bin/activate && pip install -r {REQUIREMENTS_FILE}'", shell=True, check=True)

            except subprocess.CalledProcessError:
                console.print("[red]❌ Автоматическая установка зависимостей не удалась. Проверьте систему вручную.[/red]")


# --- Установка службы для проекта ---
def setup_service():
    working_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(working_dir, VENV_NAME, "bin", "python3")
    main_script = os.path.join(working_dir, MAIN_SCRIPT)
    service_user = config.get('PROJECT', 'user', 'root')
    service_description = config.get('PROJECT', 'description', 'My Project Service')

    service_content = f"""[Unit]
Description={service_description}
After=network.target

[Service]
Type=simple
User={service_user}
WorkingDirectory={working_dir}
ExecStart={venv_python} {main_script}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""

    service_file_path = f"/etc/systemd/system/{SERVICE_NAME}.service"
    
    try:
        result = subprocess.run(f"systemctl is-enabled {SERVICE_NAME}.service", shell=True, capture_output=True)
        
        if result.returncode == 0:
            console.print(f"[yellow]Служба '{SERVICE_NAME}.service' уже существует и активирована.[/yellow]")
            return
        
    except subprocess.CalledProcessError:
        pass

    try:
        with console.status("[yellow]⚙️ Создаю systemd сервис...[/yellow]"):
            with open(service_file_path, "w") as f:
                f.write(service_content)
            
            console.print("[green]✅ Сервис создан успешно.[/green]")
            console.status("[blue]Перезагружаю systemd...[/blue]")
            
            subprocess.run("systemctl daemon-reload", shell=True, check=True)
            subprocess.run(f"systemctl enable {SERVICE_NAME}.service", shell=True, check=True)
            subprocess.run(f"systemctl start {SERVICE_NAME}.service", shell=True, check=True)
            
            console.print("[green]✅ Служба запущена и активирована.[/green]")
    
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при создании или запуске службы: {e}[/red]")


# --- Установка необходимых пакетов ---
def install_certbot():
    console.status(f"[blue]🔧 Установка необходимых пакетов для certbot через {SYSTEM_INFO['package_manager']}...[/blue]")
    try:
        if SYSTEM_INFO['package_manager'] == 'apt':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} certbot", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'dnf':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} certbot", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'pacman':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} certbot", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'zypper':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} certbot", shell=True, check=True)
        else:
            subprocess.run("apt install -y certbot", shell=True, check=True)
        
        console.print(f"[green]✅ Certbot успешно установлен через {SYSTEM_INFO['package_manager']}.[/green]")
    except subprocess.CalledProcessError:
        console.print(f"[red]❌ Ошибка при установке certbot через {SYSTEM_INFO['package_manager']}.[/red]")
        console.print("[yellow]⚠️ Попробуйте установить вручную или проверьте права доступа.[/yellow]")


# --- Получение сертификата через certbot ---
def obtain_cert(domain):
    console.status(f"[blue]🔧 Получение сертификата для домена {domain}...[/blue]")
    try:
        subprocess.run(f"certbot certonly --standalone --agree-tos --register-unsafely-without-email -d {domain}", shell=True, check=True)
        
        cert_dir = f"/etc/letsencrypt/live/{domain}/"
        
        console.print(f"[green]✅ Сертификат для {domain} успешно получен.[/green]")
        console.print(f"[blue]🔑 Файлы сертификатов находятся в директории: {cert_dir}[/blue]")
        console.print(f"[blue]fullchain.pem - {cert_dir}fullchain.pem[/blue]")
        console.print(f"[blue]privkey.pem - {cert_dir}privkey.pem[/blue]")

        return True
    except subprocess.CalledProcessError:
        console.print(f"[red]❌ Ошибка при получении сертификата для {domain}.[/red]")
        return False


# --- Создание скрипта для обновления сертификатов ---
def create_renew_script():
    renew_script = f"""#!/bin/bash

# Скрипт автоматического обновления SSL-сертификатов
LOG_FILE="/var/log/certbot-renew.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== $(date): Начало обновления сертификатов ==="

if ! command -v certbot &> /dev/null; then
    echo "ОШИБКА: certbot не найден в системе"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
    echo "ОШИБКА: Скрипт должен выполняться от имени root"
    exit 1
fi

log_message() {{
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1"
}}

check_service() {{
    local service=$1
    if systemctl is-active --quiet "$service"; then
        log_message "Служба $service активна"
        return 0
    else
        log_message "Служба $service неактивна"
        return 1
    fi
}}

restart_service() {{
    local service=$1
    if check_service "$service"; then
        log_message "Перезапуск службы $service..."
        if systemctl restart "$service"; then
            log_message "Служба $service успешно перезапущена"
        else
            log_message "ОШИБКА: Не удалось перезапустить службу $service"
            return 1
        fi
    fi
}}

log_message "Остановка nginx..."
if check_service "nginx"; then
    systemctl stop nginx
    log_message "Nginx остановлен"
else
    log_message "Nginx уже остановлен"
fi

sleep 5

if netstat -tlnp | grep ":80 " > /dev/null; then
    log_message "ПРЕДУПРЕЖДЕНИЕ: Порт 80 все еще занят"
    sleep 10
fi

log_message "Обновление сертификатов через certbot..."
if certbot renew --standalone --quiet --non-interactive; then
    log_message "Сертификаты успешно обновлены"
else
    log_message "ОШИБКА: Не удалось обновить сертификаты"
    systemctl start nginx
    exit 1
fi

log_message "Запуск nginx..."
if systemctl start nginx; then
    log_message "Nginx успешно запущен"
else
    log_message "ОШИБКА: Не удалось запустить nginx"
    exit 1
fi

log_message "Проверка конфигурации nginx..."
if nginx -t; then
    log_message "Конфигурация nginx корректна"
else
    log_message "ОШИБКА: Конфигурация nginx некорректна"
    exit 1
fi

log_message "Перезапуск основного сервиса..."

log_message "Проверка статуса служб..."
check_service "nginx"

if [[ -f "$LOG_FILE" ]]; then
    tail -n 1000 "$LOG_FILE" > "${{LOG_FILE}}.tmp" && mv "${{LOG_FILE}}.tmp" "$LOG_FILE"
fi

log_message "=== Обновление сертификатов завершено успешно ==="
echo ""

logger -t "certbot-renew" "Обновление SSL-сертификатов завершено успешно"

exit 0
"""
    
    script_path = config.get('CERTBOT', 'renew_script_path', '/root/certbot-renew.sh')
    
    try:
        with open(script_path, "w") as file:
            file.write(renew_script)
        subprocess.run(f"chmod +x {script_path}", shell=True, check=True)
        console.print(f"[green]✅ Скрипт для обновления сертификатов создан: {script_path}[/green]")
    except Exception as e:
        console.print(f"[red]❌ Ошибка при создании скрипта: {e}[/red]")


# --- Добавление задачи в crontab ---
def add_cron_task():
    cron_schedule = config.get('CERTBOT', 'cron_schedule', '0 3 * * *')
    script_path = config.get('CERTBOT', 'renew_script_path', '/root/certbot-renew.sh')
    
    try:
        result = subprocess.run("crontab -l 2>/dev/null", shell=True, capture_output=True, text=True)
        if result.returncode == 0 and script_path in result.stdout:
            console.print("[yellow]⚠️ Задача для обновления сертификатов уже добавлена в crontab.[/yellow]")
            return
    except subprocess.CalledProcessError:
        pass
    
    cron_task = f"# Автоматическое обновление SSL-сертификатов\n{cron_schedule} {script_path}"
    
    try:
        if result.returncode == 0:
            new_crontab = result.stdout + "\n" + cron_task
        else:
            new_crontab = cron_task
        
        with open("/tmp/new_crontab", "w") as f:
            f.write(new_crontab)
        
        subprocess.run("crontab /tmp/new_crontab", shell=True, check=True)
        subprocess.run("rm -f /tmp/new_crontab", shell=True)
        
        console.print("[green]✅ Задача для автоматического обновления сертификатов добавлена в crontab.[/green]")
        console.print(f"[blue]📅 Расписание: {cron_schedule}[/blue]")
        console.print(f"[blue]📝 Скрипт: {script_path}[/blue]")
        
        console.print("\n[yellow]📋 Текущий crontab:[/yellow]")
        subprocess.run("crontab -l", shell=True)
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка при добавлении cron задачи: {e}[/red]")
        console.print("[yellow]⚠️ Попробуйте добавить задачу вручную:[/yellow]")
        console.print(f"[blue]crontab -e[/blue]")
        console.print(f"[blue]Добавьте строку: {cron_task}[/blue]")


# --- Основная функция ---
def setup_certbot():
    install_certbot()
    domain = Prompt.ask("[bold blue]Введите домен для получения сертификата[/bold blue]")
    if obtain_cert(domain):
        create_renew_script()
        add_cron_task()
    else:
        console.print("[red]❌ Сертификат не был получен, дальнейшие шаги не выполнены.[/red]")


def install_nginx():
    console.print("[blue]🔧 Установка и настройка Nginx...[/blue]")
    try:
        if SYSTEM_INFO['package_manager'] == 'apt':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} nginx", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'dnf':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} nginx", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'pacman':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} nginx", shell=True, check=True)
        elif SYSTEM_INFO['package_manager'] == 'zypper':
            subprocess.run(f"{SYSTEM_INFO['install_cmd']} nginx", shell=True, check=True)
        else:
            subprocess.run("apt install -y nginx", shell=True, check=True)

        nginx_target_path = config.get('NGINX', 'target_path', '/etc/nginx/nginx.conf')
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_nginx_conf = os.path.join(current_dir, config.get('NGINX', 'config_template', 'nginx.conf'))

        if not os.path.exists(local_nginx_conf):
            console.print("[red]❌ Файл nginx.conf не найден в текущей директории.[/red]")
            return

        with open(local_nginx_conf) as f:
            config_content = f.read()

        current_domain = None
        for line in config_content.splitlines():
            if "server_name" in line and "$" not in line:
                parts = line.strip().split()
                if len(parts) >= 2:
                    current_domain = parts[1].strip(";")
                    break

        if current_domain:
            console.print(f"[yellow]🔍 Найден домен в конфиге: {current_domain}[/yellow]")

        new_domain = Prompt.ask("[bold blue]Введите домен для Nginx[/bold blue]")

        if current_domain and current_domain != new_domain:
            config_content = config_content.replace(current_domain, new_domain)
            console.print(f"[green]✅ Заменили домен {current_domain} на {new_domain}[/green]")
        else:
            console.print(f"[green]✅ Домен установлен как {new_domain}[/green]")

        temp_path = "/tmp/nginx_temp.conf"
        with open(temp_path, "w") as f:
            f.write(config_content)

        subprocess.run(f"cp {temp_path} {nginx_target_path}", shell=True, check=True)
        result = subprocess.run("nginx -t", shell=True, capture_output=True, text=True)

        if result.returncode == 0:
            console.print("[green]✅ Конфигурация Nginx корректна.[/green]")
            subprocess.run("systemctl restart nginx", shell=True, check=True)
            console.print("[green]🚀 Nginx успешно перезапущен с новой конфигурацией.[/green]")
        else:
            console.print("[red]❌ Ошибка в конфигурации Nginx:[/red]")
            console.print(result.stderr)
            console.print("[yellow]⚠️ Изменения не были применены.[/yellow]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]❌ Ошибка: {e}[/red]")


def configure_project():
    console.print("[blue]⚙️ Настройка конфигурации проекта...[/blue]")
    
    project_name = Prompt.ask("[bold blue]Название проекта[/bold blue]", default=config.get('PROJECT', 'name', 'myproject'))
    main_script = Prompt.ask("[bold blue]Главный скрипт[/bold blue]", default=config.get('PROJECT', 'main_script', 'main.py'))
    requirements_file = Prompt.ask("[bold blue]Файл зависимостей[/bold blue]", default=config.get('PROJECT', 'requirements_file', 'requirements.txt'))
    venv_name = Prompt.ask("[bold blue]Имя виртуального окружения[/bold blue]", default=config.get('PROJECT', 'venv_name', 'venv'))
    service_name = Prompt.ask("[bold blue]Имя службы systemd[/bold blue]", default=config.get('PROJECT', 'service_name', 'myproject'))
    service_user = Prompt.ask("[bold blue]Пользователь для службы[/bold blue]", default=config.get('PROJECT', 'user', 'root'))
    service_description = Prompt.ask("[bold blue]Описание службы[/bold blue]", default=config.get('PROJECT', 'description', 'My Project Service'))
    
    config.set('PROJECT', 'name', project_name)
    config.set('PROJECT', 'main_script', main_script)
    config.set('PROJECT', 'requirements_file', requirements_file)
    config.set('PROJECT', 'venv_name', venv_name)
    config.set('PROJECT', 'service_name', service_name)
    config.set('PROJECT', 'user', service_user)
    config.set('PROJECT', 'description', service_description)
    
    global SERVICE_NAME, MAIN_SCRIPT, REQUIREMENTS_FILE, VENV_NAME
    SERVICE_NAME = service_name
    MAIN_SCRIPT = main_script
    REQUIREMENTS_FILE = requirements_file
    VENV_NAME = venv_name
    
    console.print("[green]✅ Конфигурация проекта обновлена.[/green]")


def show_system_info():
    """Показывает информацию о системе и определенном пакетном менеджере"""
    console.print("\n[bold magenta]🖥️ Информация о системе[/bold magenta]\n")
    
    console.print(f"[blue]Операционная система:[/blue] {platform.system()} {platform.release()}")
    console.print(f"[blue]Архитектура:[/blue] {platform.machine()}")
    console.print(f"[blue]Python версия:[/blue] {platform.python_version()}")
    
    if SYSTEM_INFO['distro']:
        console.print(f"[blue]Дистрибутив:[/blue] {SYSTEM_INFO['distro']}")
    
    console.print(f"[blue]Пакетный менеджер:[/blue] {SYSTEM_INFO['package_manager']}")
    console.print(f"[blue]Команда обновления:[/blue] {SYSTEM_INFO['update_cmd']}")
    console.print(f"[blue]Команда установки:[/blue] {SYSTEM_INFO['install_cmd']}")
    
    try:
        result = subprocess.run(f"which {SYSTEM_INFO['package_manager']}", shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            console.print(f"[green]✅ {SYSTEM_INFO['package_manager']} доступен в системе[/green]")
        else:
            console.print(f"[red]❌ {SYSTEM_INFO['package_manager']} не найден в системе[/red]")
    except Exception as e:
        console.print(f"[red]❌ Ошибка при проверке {SYSTEM_INFO['package_manager']}: {e}[/red]")
    
    console.print(f"\n[yellow]💡 Примеры использования:[/yellow]")
    console.print(f"  Обновление пакетов: [bold]{SYSTEM_INFO['update_cmd']}[/bold]")
    console.print(f"  Установка пакета: [bold]{SYSTEM_INFO['install_cmd']} имя_пакета[/bold]")
    
    console.print("\n[dim]Нажмите Enter для возврата в меню...[/dim]")
    input()


def show_help():
    console.print(
        "\n[bold magenta]📘 Инструкция по использованию менеджера[/bold magenta]\n"
    )

    console.print(
        "[green]🔹 При первичной установке рекомендуется выполнять шаги по порядку — сверху вниз.[/green]\n"
    )

    console.print(
        "🔐 [yellow]Если вы уже получали SSL-сертификат другим способом[/yellow], не забудьте вручную указать путь к нему в конфигурации Nginx:\n"
        "  ➤ Файл: [bold]/папка с проектом/nginx.conf[/bold]\n"
        "  ➤ Укажите параметры до запуска настройки, [italic]ssl_certificate[/italic] и [italic]ssl_certificate_key[/italic]\n"
    )

    console.print(
        "⚠️ [cyan]Если вы используете Certbot[/cyan] (рекомендуется), сертификаты будут размещены в каталоге:\n"
        "  ➤ [bold]/etc/letsencrypt/live/ВАШ_ДОМЕН/[/bold]\n"
        "  🔁 Автоматическое продление настроено — вам не нужно делать это вручную.\n"
    )

    console.print(
        "\n[dim]💡 Подсказка: Вернутся в главное меню, сочетание клавиш- Ctrl+C.[/dim]\n"
    )


# --- Отображение меню ---
def show_menu():
    if os.geteuid() != 0:
        console.print("[bold red]⛔ Требуется запуск от имени root или через sudo[/bold red]")
        sys.exit(1)
    
    table = Table(
        title=f"🧰 [bold]Менеджер установки и управления проектом: {config.get('PROJECT', 'name', 'myproject')}[/bold]\n[dim]Система: {SYSTEM_INFO['distro'] or 'Unknown'} | Пакетный менеджер: {SYSTEM_INFO['package_manager']}[/dim]",
        title_style="bold magenta",
        header_style="bold blue",
    )

    table.add_column("№", justify="center", style="bold cyan", no_wrap=True)
    table.add_column("Действие", style="bold white")
    table.add_row("0", "📘 Показать инструкцию")
    table.add_row("1", "⚙️  Настроить конфигурацию проекта")
    table.add_row("2", "📦 Установить зависимости [dim](pip install)[/dim]")
    table.add_row("3", "🔐 Получить SSL-сертификат [yellow]Certbot[/yellow]")
    table.add_row("4", "🖧 Установить и настроить [green]Nginx[/green]")
    table.add_row("5", "🐍 Запустить вручную  [italic]venv/bin/python3 main.py[/italic]")
    table.add_row("6", "⚙️  Установить службу [dim](systemd)[/dim]")
    table.add_row("7", "🔄 Перезапустить службу [dim](systemd)[/dim")
    table.add_row("8", "🛑 Остановить [dim](systemd)[/dim]")
    table.add_row("9", "📜 Просмотреть логи")
    table.add_row("10", "📊 Показать статус службы")
    table.add_row("11", "📜 Логи обновления сертификатов")
    table.add_row("12", "🖥️  Информация о системе")
    table.add_row("13", "🚪 Выход")

    console.print(table)

    try:
        while True:
            choice = Prompt.ask(
                "[bold blue]🔹 Выберите номер действия[/bold blue]",
                choices=[str(i) for i in range(14)],
                show_choices=False
            )
            
            if choice == "0":
                show_help()
            elif choice == "1":
                configure_project()
            elif choice == "2":
                install_dependencies()
            elif choice == "3":
                setup_certbot()
            elif choice == "4":
                install_nginx()
            elif choice == "5":
                if Confirm.ask("[green]Вы действительно хотите запустить проект вручную?[/green]"):
                    os.system(f"{VENV_NAME}/bin/python3 {MAIN_SCRIPT}")
            elif choice == "6":
                setup_service()
            elif choice == "7":
                if Confirm.ask("[yellow]Вы действительно хотите перезапустить службу?[/yellow]"):
                    os.system(f"systemctl restart {SERVICE_NAME}")
            elif choice == "8":
                if Confirm.ask("[red]Вы уверены, что хотите остановить службу?[/red]"):
                    os.system(f"systemctl stop {SERVICE_NAME}")
            elif choice == "9":
                os.system(f"journalctl -u {SERVICE_NAME} -n 50 --no-pager")
            elif choice == "10":
                os.system(f"systemctl status {SERVICE_NAME}")
            elif choice == "11":
                log_file = "/var/log/certbot-renew.log"
                if os.path.exists(log_file):
                    console.print(f"[blue]📜 Последние 50 строк логов обновления сертификатов:[/blue]")
                    os.system(f"tail -n 50 {log_file}")
                else:
                    console.print("[yellow]⚠️ Файл логов обновления сертификатов не найден.[/yellow]")
            elif choice == "12":
                show_system_info()
            elif choice == "13":
                console.print("[green]✅ Выход из программы.[/green]")
                sys.exit(0)
            
            console.print("\n[dim]--- Нажмите Ctrl+C для выхода в меню ---[/dim]\n")
    except KeyboardInterrupt:
        console.print("\n[bold green]⏹ Выход в главное меню.[/bold green]")


if __name__ == "__main__":
    while True:
        show_menu()
