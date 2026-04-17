# Инструкция по настройке и миграции бота на Linux сервер

## Обзор

Эта инструкция описывает процесс настройки Ubuntu 22.04 сервера и миграции Telegram бота с Windows на Linux.

## Предварительные требования

- Ubuntu 22.04 LTS сервер с публичным IP
- Доступ по SSH (root или пользователь с sudo правами)
- Минимум 2GB RAM, 2 CPU ядра, 30GB диска

## Шаг 1: Подключение к серверу

```bash
ssh root@149.33.0.41
# Введите пароль
```

## Шаг 2: Автоматическая настройка сервера

Скопируйте скрипт на сервер и выполните:

```bash
# На локальной машине (Windows)
scp scripts/setup_linux_server.sh root@149.33.0.41:/root/

# На сервере
chmod +x /root/setup_linux_server.sh
bash /root/setup_linux_server.sh
```

Скрипт автоматически установит:
- Python 3.11+
- PostgreSQL
- Redis
- Все необходимые системные библиотеки
- Создаст пользователя `gptbot` и директорию `/opt/gptbot`

## Шаг 3: Проверка доступности сервисов

```bash
# Скопируйте скрипт проверки
scp scripts/check_services.sh root@149.33.0.41:/root/

# На сервере
chmod +x /root/check_services.sh
bash /root/check_services.sh
```

Убедитесь, что:
- ✓ YooKassa API доступен
- ✓ OpenAI API доступен
- ✓ PostgreSQL работает
- ✓ Redis работает

## Шаг 4: Копирование кода бота на сервер

### Вариант 1: Через git (если код в репозитории)

```bash
# На сервере
cd /opt/gptbot
git clone <URL_РЕПОЗИТОРИЯ> .
chown -R gptbot:gptbot /opt/gptbot
```

### Вариант 2: Через scp (если код локально)

```bash
# На локальной машине (Windows)
# Создайте архив проекта (исключая venv, __pycache__, .env)
# Или используйте rsync если установлен

scp -r K:\GPTBOT\* root@149.33.0.41:/opt/gptbot/
# Исключите ненужные файлы (.env, venv, __pycache__)

# На сервере
chown -R gptbot:gptbot /opt/gptbot
```

### Вариант 3: Через tar архив

```bash
# На локальной машине (Windows, в PowerShell)
cd K:\GPTBOT
tar --exclude='venv' --exclude='__pycache__' --exclude='.env' --exclude='*.pyc' -czf gptbot.tar.gz .

# Копируем на сервер
scp gptbot.tar.gz root@149.33.0.41:/opt/

# На сервере
cd /opt
tar -xzf gptbot.tar.gz -C /opt/gptbot
chown -R gptbot:gptbot /opt/gptbot
rm gptbot.tar.gz
```

## Шаг 5: Создание виртуального окружения Python

```bash
# Переключаемся на пользователя gptbot
su - gptbot
cd /opt/gptbot

# Создаем виртуальное окружение
python3 -m venv venv

# Активируем окружение
source venv/bin/activate

# Обновляем pip
pip install --upgrade pip setuptools wheel
```

## Шаг 6: Установка зависимостей

```bash
# Убедитесь, что виртуальное окружение активно
source venv/bin/activate

# Устанавливаем зависимости
pip install -r requirements.txt
```

**Примечание:** Установка может занять 10-20 минут, особенно для пакетов с машинным обучением (insightface, opencv-python, rembg).

## Шаг 7: Настройка переменных окружения

```bash
# Создаем .env файл
nano /opt/gptbot/.env
```

Скопируйте содержимое вашего `.env` файла с Windows, но **обновите** следующие параметры:

```env
# База данных (локальная на сервере)
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app

# Redis (локальный на сервере)
REDIS_URL=redis://localhost:6379/0

# Публичный URL API (замените на IP вашего сервера)
PUBLIC_BASE_URL=http://149.33.0.41:8000
# Или если есть домен:
# PUBLIC_BASE_URL=https://yourdomain.com

# Остальные настройки остаются теми же:
BOT_TOKEN=your_bot_token
OPENAI_API_KEY=your_openai_key
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
ADMIN_IDS=your_admin_ids
```

Сохраните файл: `Ctrl+O`, `Enter`, `Ctrl+X`

## Шаг 8: Применение миграций базы данных

```bash
# Убедитесь, что виртуальное окружение активно
source venv/bin/activate

# Применяем миграции
alembic upgrade head
```

Если возникнут ошибки с правами доступа, выполните:

```bash
# От имени root
sudo -u postgres psql -d app <<EOF
GRANT ALL PRIVILEGES ON DATABASE app TO app;
GRANT ALL ON SCHEMA public TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app;
\q
EOF
```

## Шаг 9: Настройка systemd сервисов для автозапуска

```bash
# Копируем service файлы
cp scripts/gptbot-api.service /etc/systemd/system/
cp scripts/gptbot-bot.service /etc/systemd/system/

# Перезагружаем systemd
systemctl daemon-reload

# Включаем автозапуск
systemctl enable gptbot-api.service
systemctl enable gptbot-bot.service

# Запускаем сервисы
systemctl start gptbot-api.service
systemctl start gptbot-bot.service
```

## Шаг 10: Проверка работы сервисов

```bash
# Проверка статуса
systemctl status gptbot-api.service
systemctl status gptbot-bot.service

# Просмотр логов
journalctl -u gptbot-api.service -f
journalctl -u gptbot-bot.service -f

# Проверка API
curl http://localhost:8000/health
# Должно вернуть: {"status":"ok"}
```

## Шаг 11: Настройка файрвола (если нужно)

```bash
# Разрешаем входящие соединения на порт 8000 (для API)
ufw allow 8000/tcp

# Или если используете iptables
iptables -A INPUT -p tcp --dport 8000 -j ACCEPT
```

## Управление сервисами

```bash
# Запуск
systemctl start gptbot-api.service
systemctl start gptbot-bot.service

# Остановка
systemctl stop gptbot-api.service
systemctl stop gptbot-bot.service

# Перезапуск
systemctl restart gptbot-api.service
systemctl restart gptbot-bot.service

# Просмотр логов
journalctl -u gptbot-api.service -n 100
journalctl -u gptbot-bot.service -n 100

# Просмотр логов в реальном времени
journalctl -u gptbot-api.service -f
journalctl -u gptbot-bot.service -f
```

## Миграция данных с Windows сервера

Если нужно перенести данные из базы данных с Windows:

```bash
# На Windows сервере (в PowerShell)
pg_dump -h localhost -U app -d app > backup.sql

# Копируем на Linux сервер
scp backup.sql root@149.33.0.41:/opt/

# На Linux сервере
sudo -u postgres psql -d app < /opt/backup.sql
```

## Решение проблем

### Проблема: Сервисы не запускаются

```bash
# Проверьте логи
journalctl -u gptbot-api.service -n 50
journalctl -u gptbot-bot.service -n 50

# Проверьте права доступа
ls -la /opt/gptbot
chown -R gptbot:gptbot /opt/gptbot

# Проверьте .env файл
cat /opt/gptbot/.env
```

### Проблема: База данных недоступна

```bash
# Проверьте статус PostgreSQL
systemctl status postgresql

# Проверьте подключение
sudo -u postgres psql -d app -c "SELECT 1;"

# Проверьте настройки в .env
grep DATABASE_URL /opt/gptbot/.env
```

### Проблема: Redis недоступен

```bash
# Проверьте статус Redis
systemctl status redis-server

# Проверьте подключение
redis-cli ping
```

### Проблема: YooKassa или OpenAI недоступны

```bash
# Запустите скрипт проверки
bash /root/check_services.sh

# Проверьте вручную
curl -I https://api.yookassa.ru/v3
curl -I https://api.openai.com/v1/models
```

## Обновление кода

```bash
# Переключаемся на пользователя gptbot
su - gptbot
cd /opt/gptbot

# Останавливаем сервисы
sudo systemctl stop gptbot-api.service
sudo systemctl stop gptbot-bot.service

# Обновляем код (через git или копирование)
git pull
# или
# scp новые файлы

# Обновляем зависимости (если requirements.txt изменился)
source venv/bin/activate
pip install -r requirements.txt

# Применяем миграции (если есть новые)
alembic upgrade head

# Запускаем сервисы
sudo systemctl start gptbot-api.service
sudo systemctl start gptbot-bot.service
```

## Резервное копирование

```bash
# Бэкап базы данных
sudo -u postgres pg_dump app > /opt/backups/db_$(date +%Y%m%d_%H%M%S).sql

# Бэкап .env файла
cp /opt/gptbot/.env /opt/backups/env_$(date +%Y%m%d_%H%M%S).backup
```

## Безопасность

1. **Измените пароль root:**
   ```bash
   passwd root
   ```

2. **Настройте SSH ключи вместо паролей:**
   ```bash
   # На локальной машине
   ssh-keygen -t ed25519
   ssh-copy-id root@149.33.0.41
   ```

3. **Отключите вход по паролю в SSH:**
   ```bash
   nano /etc/ssh/sshd_config
   # PasswordAuthentication no
   systemctl restart sshd
   ```

4. **Настройте файрвол:**
   ```bash
   ufw enable
   ufw allow 22/tcp  # SSH
   ufw allow 8000/tcp # API (если нужно извне)
   ```

## Готово!

После выполнения всех шагов ваш бот должен работать на Linux сервере. Проверьте:
- API доступен: `curl http://149.33.0.41:8000/health`
- Бот отвечает в Telegram
- Платежи YooKassa работают

