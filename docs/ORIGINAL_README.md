Telegram GPT-5 Bot

## 📁 Структура проекта

- `app/` — исходный код бота и API
- `app/bot/` — Telegram-бот (Aiogram 3)
- `app/api/` — FastAPI (вебхуки ЮKassa, health)
- `app/db/` — SQLAlchemy, Alembic
- `app/services/` — интеграции (LLM, аудио, биллинг, платежи)
- `app/admin/` — простая админка
- `app/utils/` — утилиты
- `scripts/` — скрипты для запуска, остановки и настройки автозапуска (Windows)

## 🚀 Быстрый старт

### Вариант 1: Запуск через Docker Compose (рекомендуется)

1. **Создайте файл `.env`** на основе `.env.example`:
```bash
cp .env.example .env
```

2. **Настройте переменные окружения** в файле `.env`:
   - `BOT_TOKEN` — токен Telegram-бота (получить у [@BotFather](https://t.me/BotFather))
   - `OPENAI_API_KEY` — ключ OpenAI API
   - `ADMIN_IDS` — список Telegram ID администраторов через запятую или пробел (например, `ADMIN_IDS=1177786625 123456789`)
   - `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` — для работы платежей (опционально)
   - `PUBLIC_BASE_URL` — публичный URL вашего API (для вебхуков, например `https://yourdomain.com`)

3. **Запустите все сервисы**:
```bash
docker-compose up -d
```

4. **Примените миграции базы данных**:
```bash
docker-compose exec api alembic upgrade head
```

5. **Проверьте статус сервисов**:
```bash
docker-compose ps
```

6. **Просмотр логов**:
```bash
# Все сервисы
docker-compose logs -f

# Только бот
docker-compose logs -f bot

# Только API
docker-compose logs -f api
```

### Вариант 2: Локальный запуск (для разработки)

#### Требования
- Python 3.11+
- PostgreSQL 16+
- Redis 7+

#### Шаги запуска

1. **Установите зависимости**:
```bash
pip install -r requirements.txt
```

2. **Настройте базу данных PostgreSQL**:
   - Создайте базу данных: `CREATE DATABASE app;`
   - Или используйте настройки из `docker-compose.yml` (пользователь: `app`, пароль: `app`, БД: `app`)

3. **Создайте файл `.env`** (см. `.env.example`):
```env
BOT_TOKEN=your_bot_token_here
OPENAI_API_KEY=your_openai_key_here
ADMIN_IDS=1177786625 123456789
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/app
REDIS_URL=redis://localhost:6379/0
PUBLIC_BASE_URL=http://localhost:8000
```

4. **Примените миграции** (из корня проекта):
```bash
python -m alembic upgrade head
```

5. **Запустите Redis** (если не используете Docker):
```bash
# Windows (через WSL или установленный Redis)
redis-server

# Linux/Mac
redis-server
```

6. **Запустите API** (в отдельном терминале):
```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

7. **Запустите бота** (в отдельном терминале):
```bash
python -m app.bot.main
```

### Проверка работоспособности

- **API**: откройте в браузере `http://localhost:8000/health` — должен вернуть `{"status": "ok"}`
- **Бот**: найдите вашего бота в Telegram и отправьте `/start`

## ⚙️ Переменные окружения

См. `.env.example` для полного списка переменных. Основные:

- `BOT_TOKEN` — токен Telegram-бота
- `OPENAI_API_KEY` — ключ OpenAI
- `ADMIN_IDS` — список Telegram ID администраторов через запятую или пробел
- `DATABASE_URL` — строка подключения к PostgreSQL
- `REDIS_URL` — строка подключения к Redis
- `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY` — для платежей (опционально)
- `TELEGRAM_PAYMENT_TOKEN` — провайдер токен Telegram Payments (от ЮKassa)
- `PUBLIC_BASE_URL` — публичный URL API для вебхуков (например, `https://yourdomain.com`)
- `API_INTERNAL_URL` — внутренний URL для обращения бота к API (на продакшене обычно `http://127.0.0.1:8000`)

> Тестовые значения ЮKassa (для отладки):
> - `YOOKASSA_SHOP_ID=1209585`
> - `YOOKASSA_SECRET_KEY=test_pvoeu4FxEDdK1E2nMFcYeRELlmlQkkq20VZ1nihY4Wk`
> - `TELEGRAM_PAYMENT_TOKEN=381764678:TEST:151363`

При переходе на продакшен замените их на боевые значения из личного кабинета ЮKassa / BotFather.

## Диалоги бота

В разделе «Диалоги» доступны четыре преднастроенных сценария:

- `💬 Общение` — дружелюбный ассистент для свободного разговора.
- `🔍 Анализ текста` — помогает улучшать тексты и даёт рекомендации.
- `🌐 Переводчик` — автоматическое определение языка, переводы в выбранный язык и пояснения.
- `📝 Генератор промптов` — формирует промпты для генераторов изображений (русский + английский варианты).

Каждый диалог хранит историю сообщений, поддерживает очистку (`/clear` или кнопка «🧹 Очистить историю») и завершение (`/end`, «❌ Закрыть диалог» или «↩️ Назад к диалогам»).

## FaceSwap

В главном меню доступен раздел `🎭 FaceSwap`. Он позволяет заменить лицо на фотографии при помощи GPT-5:

- Отправьте фото с лицом, которое нужно заменить, затем своё фото.
- Либо прикрепите две фотографии сразу (в одном сообщении/альбоме).
- Бот проверит, что на снимках реальные люди, выполнит FaceSwap и спишет фиксированную стоимость — 7 500 токенов.
- По завершении бот вернёт готовый результат и возможные предупреждения.

## Оживление фото

В разделе `✂️ Работа с фото` доступна функция `🎬 Оживить фото`, которая создаёт видео из статичного фото с использованием KLING-V2 API:

- Выберите режим (Стандарт 720p или Про 1080p) и длительность (5с или 10с).
- Отправьте ваше фото, которое нужно оживить.
- Отправьте пример видео (например, где танцует мальчик).
- Напишите текстовое описание того, как нужно оживить фото.
- Бот создаст видео, применяя движение из примера к вашему фото.
- Стоимость: 10 токенов (для теста, может быть изменено в настройках).

## Админ-панель

Пользователи из `ADMIN_IDS` видят в главном меню кнопку `👑 Админка`. Через неё доступны:

- просмотр административного меню;
- пополнение баланса пользователя по его Telegram ID;
- просмотр статистики всех пользователей (ID, никнейм, баланс токенов);
- проверка баланса пользователя;
- списание токенов у пользователя;
- просмотр статистики использования.

Процесс пополнения:

1. Нажать `👑 Админка` → «Пополнить счёт пользователя».
2. Ввести TG ID (числом).
3. Ввести количество токенов.
4. После подтверждения бот отобразит новый баланс выбранного пользователя.

## 🔄 Обновление на продакшене

### Шаги для применения обновлений:

1. **Остановите бота и API** (если запущены):
```bash
# Если через Docker
docker-compose down

# Если локально - остановите процессы (Ctrl+C в терминалах)
```

2. **Примените миграции БД** (если есть изменения структуры):
```bash
# Локально
python -m alembic upgrade head

# Или через Docker
docker-compose exec api alembic upgrade head
```

3. **Перезапустите сервисы**:
```bash
# Если через Docker
docker-compose up -d

# Если локально - запустите заново:
# Терминал 1: redis-server (если не запущен)
# Терминал 2: uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
# Терминал 3: python -m app.bot.main
```

**⚠️ ВАЖНО**: После обновления кода **ОБЯЗАТЕЛЬНО** перезапустите бота, иначе изменения не применятся!

### Проверка текущей версии миграций:
```bash
python -m alembic current
```

### Текущие миграции:
- `0001_init` — создание всех таблиц (users, balances, usage, payments, promocodes, referrals, dialogs, messages)
- `0002_add_usage_success` — добавление полей `success` и `error_message` в таблицу `usage`
- `0003_add_promo_discount` — добавление полей `discount_percent` и `created_at` в таблицу `promocodes`
- `0004_tg_payment_charge_id` — добавление поля `telegram_payment_charge_id` в таблицу `payments`
- `0005_add_promocode_usage` — создание таблицы `promocode_usage` для отслеживания использования промокодов
- `0006_sub_notifications` — создание таблицы `subscription_notifications` для отслеживания уведомлений о подписке
- `0007_promo_valid_days` — добавление поля `valid_days` в таблицу `promocodes` (количество дней действия промокода)

### ⚠️ Решение проблемы с правами доступа при миграциях

Если при выполнении миграций возникает ошибка:
```
sqlalchemy.exc.ProgrammingError: (psycopg.errors.InsufficientPrivilege) нужно быть владельцем таблицы
```

Это означает, что пользователь базы данных не имеет прав на изменение структуры таблиц.

**Решение:**

1. **Подключитесь к PostgreSQL от имени суперпользователя** (обычно `postgres`):
```bash
psql -h localhost -U postgres -d gptbot
```

2. **Выполните SQL-скрипт для исправления прав**:
```bash
psql -h localhost -U postgres -d gptbot -f scripts/fix_promocodes_permissions.sql
```

Или выполните SQL-команды вручную:
```sql
-- Изменить владельца таблицы на пользователя 'app'
ALTER TABLE promocodes OWNER TO app;

-- Если нужно, выдать права на все таблицы в схеме public
GRANT ALL ON SCHEMA public TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app;
```

3. **Повторно выполните миграцию**:
```bash
python -m alembic upgrade head
```

**Примечание:** Если имя пользователя БД отличается от `app`, замените его в SQL-командах на актуальное имя пользователя из вашего `DATABASE_URL`.

## 🔄 Автозапуск на Windows VDS/Сервере

Для автоматического запуска бота при перезагрузке Windows VDS используйте один из вариантов ниже.

### Вариант 1: Автозапуск через Startup папку (простой способ)

**Пошаговая инструкция для сервера:**

1. **Откройте папку автозагрузки**:
   - Нажмите `Win + R` на сервере
   - Введите `shell:startup`
   - Нажмите Enter
   - Откроется папка автозагрузки (обычно `C:\Users\ВашеИмя\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup`)

2. **Настройте скрипт автозапуска**:
   - Откройте файл `scripts/autostart.bat` в текстовом редакторе
   - **ВАЖНО**: Измените путь к проекту на строке `cd /d "K:\GPTBOT"` на актуальный путь к проекту на вашем сервере
     - Например, если проект на сервере в `C:\GPTBOT`, измените на: `cd /d "C:\GPTBOT"`
     - Или если в `D:\Projects\GPTBOT`, измените на: `cd /d "D:\Projects\GPTBOT"`

3. **Создайте ярлык**:
   - Найдите файл `scripts/autostart.bat` в папке проекта
   - Правой кнопкой мыши на файле → **"Создать ярлык"**
   - Переименуйте ярлык (например, "GPT Bot Autostart")
   - **Переместите ярлык** в папку Startup (которую открыли в шаге 1)

4. **Проверка**:
   - Перезагрузите сервер или выйдите из системы и войдите снова
   - После входа в систему должны автоматически открыться 3 окна:
     - Redis Server
     - GPT Bot - API Server
     - GPT Bot - Telegram Bot
   - Проверьте работу бота: отправьте `/start` боту в Telegram

**Готово!** При каждом входе в систему бот будет запускаться автоматически.

**⚠️ Важно**: 
- Убедитесь, что PostgreSQL запускается автоматически (обычно это служба Windows, которая запускается автоматически)
- Если путь к проекту изменится, обновите путь в файле `scripts/autostart.bat`

### Вариант 2: Автозапуск через Task Scheduler (рекомендуется для VDS)

Task Scheduler более надежен, так как позволяет:
- Запускать задачи даже без входа пользователя в систему
- Настроить задержку запуска (чтобы PostgreSQL успел запуститься)
- Автоматически перезапускать при сбое

#### Настройка через графический интерфейс:

1. **Откройте Планировщик заданий**:
   - Нажмите `Win + R`
   - Введите `taskschd.msc`
   - Нажмите Enter

2. **Создайте новую задачу**:
   - В правой панели нажмите "Создать задачу..."
   - **Общие**:
     - Имя: `GPT Bot - Auto Start`
     - Отметить: "Выполнять для всех пользователей"
     - Отметить: "Выполнять с наивысшими правами"
   
   - **Триггеры** → **Создать**:
     - Начать задачу: "При входе в систему"
     - Отметить: "Включено"
     - Нажмите "ОК"
   
   - **Действия** → **Создать**:
     - Действие: "Запуск программы"
     - Программа или сценарий: укажите полный путь к `scripts\start_all.bat`
       Например: `K:\GPTBOT\scripts\start_all.bat`
     - Начало в: укажите корневую папку проекта
       Например: `K:\GPTBOT`
     - Нажмите "ОК"
   
   - **Условия**:
     - Снимите галочку "Запускать только при питании от электросети" (если нужно)
     - Отметьте "Пробуждать компьютер для выполнения задачи"
   
   - **Параметры**:
     - Отметьте "Выполнять задачу немедленно, если пропущен плановый запуск"
     - Нажмите "ОК"

3. **Создайте дополнительную задачу с задержкой** (опционально, если PostgreSQL запускается медленно):
   - Создайте еще одну задачу с тем же действием
   - В триггере установите задержку 30-60 секунд после входа в систему

#### Настройка через скрипт (самый простой способ):

1. **Запустите скрипт настройки** от имени администратора:
   - Найдите файл `scripts/setup_autostart.bat`
   - Правой кнопкой мыши → "Запуск от имени администратора"
   - Скрипт автоматически создаст задачу в Планировщике заданий

2. **Готово!** Бот будет запускаться автоматически при входе в систему.

**Для удаления автозапуска** используйте `scripts/remove_autostart.bat` (также от имени администратора).

#### Настройка через командную строку (альтернативный способ):

```cmd
schtasks /create /tn "GPT Bot - Auto Start" /tr "K:\GPTBOT\scripts\start_all.bat" /sc onlogon /rl highest /f
```

**⚠️ Важно**: Замените `K:\GPTBOT` на путь к вашему проекту!

### Использование скриптов запуска

В папке `scripts/` доступны следующие скрипты:

**Скрипты запуска:**
- **`start_all.bat`** — запускает все компоненты (Redis, API, Bot) в отдельных окнах
- **`start_redis.bat`** — запускает только Redis
- **`start_api.bat`** — запускает только API сервер
- **`start_bot.bat`** — запускает только Telegram бота
- **`stop_all.bat`** — останавливает все компоненты

**Скрипты автозапуска:**
- **`setup_autostart.bat`** — настраивает автозапуск через Task Scheduler (требует прав администратора)
- **`remove_autostart.bat`** — удаляет автозапуск из Task Scheduler (требует прав администратора)

**Скрипты диагностики YooKassa:**
- **`test_yookassa_connection.bat`** — тестирование подключения к YooKassa API (использует PowerShell)
- **`test_yookassa_simple.bat`** — упрощенная версия теста (использует Python, работает везде)
- **`test_yookassa_tcp.py`** — Python скрипт для проверки TCP соединения
- **`fix_yookassa_firewall.bat`** — настройка файрвола Windows для доступа к YooKassa (требует прав администратора)

**Примечание**: Перед использованием скриптов убедитесь, что:
1. Python установлен и доступен из командной строки
2. Все зависимости установлены (`pip install -r requirements.txt`)
3. Файл `.env` настроен правильно
4. PostgreSQL запущен (обычно как служба Windows)
5. Путь к Redis указан правильно в `start_redis.bat` (если Redis не установлен как служба)

### Проверка автозапуска

После настройки автозапуска:

1. **Перезагрузите сервер** или выйдите из системы и войдите снова
2. **Проверьте, что процессы запущены**:
   - Откройте Диспетчер задач (`Ctrl + Shift + Esc`)
   - Во вкладке "Процессы" должны быть:
     - `python.exe` (для бота и API)
     - `redis-server.exe` (если Redis не запущен как служба)
3. **Проверьте работу бота**: отправьте `/start` боту в Telegram

### Устранение проблем

**Бот не запускается автоматически:**
- Проверьте логи в окнах компонентов (если они открыты)
- Проверьте, что путь к скрипту в Task Scheduler правильный
- Убедитесь, что PostgreSQL запущен до запуска бота
- Проверьте права доступа к файлам проекта

**Ошибка "Python не найден":**
- Добавьте Python в PATH системы
- Или укажите полный путь к `python.exe` в скриптах

**Ошибка "Redis не найден":**
- Укажите правильный путь к `redis-server.exe` в `scripts/start_redis.bat`
- Или установите Redis как службу Windows

## 💾 Автоматический бэкап базы данных

Для обеспечения безопасности данных настроена система автоматического ежедневного бэкапа базы данных.

### Ручной запуск бэкапа

Для создания бэкапа вручную:

```bash
# Через Python скрипт
python scripts/backup_db.py

# Или через bat-файл (Windows)
scripts\backup_db.bat
```

Бэкап будет сохранен в папку `backups/` с именем `backup_YYYY-MM-DD_HH-MM-SS.sql`.

### Автоматическая настройка ежедневного бэкапа

Для настройки автоматического ежедневного бэкапа:

1. **Запустите скрипт настройки** от имени администратора:
   - Найдите файл `scripts/setup_backup_task.bat`
   - Правой кнопкой мыши → "Запуск от имени администратора"
   - Скрипт автоматически создаст задачу в Планировщике заданий

2. **Готово!** Бэкап будет создаваться ежедневно в 3:00 ночи.

### Требования для бэкапа

- **PostgreSQL клиент** должен быть установлен и доступен в PATH
  - На Windows: установите PostgreSQL или только клиентские утилиты
  - Команда `pg_dump` должна быть доступна из командной строки
- **Правильно настроенный `DATABASE_URL`** в файле `.env`

### Управление бэкапами

- **Хранение**: Бэкапы сохраняются в папку `backups/` в корне проекта
- **Автоочистка**: Бэкапы старше 30 дней автоматически удаляются
- **Формат**: SQL дамп в текстовом формате (можно открыть в любом текстовом редакторе)

### Восстановление из бэкапа

Для восстановления базы данных из бэкапа:

```bash
# Windows (PowerShell или CMD)
psql -h localhost -U app -d app -f backups\backup_YYYY-MM-DD_HH-MM-SS.sql

# Или с указанием пароля через переменную окружения
set PGPASSWORD=your_password
psql -h localhost -U app -d app -f backups\backup_YYYY-MM-DD_HH-MM-SS.sql
```

**⚠️ Внимание**: Восстановление из бэкапа перезапишет все данные в базе. Используйте с осторожностью!

### Устранение проблем

**Ошибка "pg_dump не найден":**
- Установите PostgreSQL клиент или добавьте путь к `pg_dump.exe` в PATH
- На Windows путь обычно: `C:\Program Files\PostgreSQL\<версия>\bin\`

**Ошибка подключения к базе данных:**
- Проверьте правильность `DATABASE_URL` в файле `.env`
- Убедитесь, что PostgreSQL запущен и доступен
- Проверьте права доступа пользователя базы данных

## 🔧 Решение проблем с подключением к YooKassa API

### Проблема: "All connection attempts failed" или "ERR_CONNECTION_TIMED_OUT"

Если при создании платежа возникает ошибка подключения к YooKassa API, выполните следующие шаги:

#### Шаг 1: Диагностика проблемы

1. **Запустите тестовый скрипт** для проверки подключения:
   ```cmd
   scripts\test_yookassa_connection.bat
   ```
   
   **Альтернатива:** Если PowerShell недоступен, используйте упрощенный скрипт:
   ```cmd
   scripts\test_yookassa_simple.bat
   ```
   
   Этот скрипт использует Python для проверки TCP соединения и работает везде, где установлен Python.

2. **Или используйте диагностический endpoint API** (если API сервер запущен):
   ```
   http://localhost:8000/api/diagnostic/yookassa
   ```

   Этот endpoint проверит:
   - DNS резолюцию для `api.yookassa.ru`
   - TCP соединение на порт 443
   - SSL handshake
   - HTTPS запрос

#### Шаг 2: Настройка файрвола Windows

Если тест показывает, что TCP соединение не устанавливается, возможно файрвол блокирует исходящие соединения:

1. **Запустите скрипт настройки файрвола** от имени администратора:
   ```cmd
   scripts\fix_yookassa_firewall.bat
   ```

   Скрипт автоматически создаст правила файрвола для доступа к IP адресам YooKassa API.

#### Шаг 3: Проверка блокировки провайдером/хостингом

Если файрвол настроен правильно, но подключение все равно не работает, возможно провайдер или хостинг блокирует доступ к российским IP адресам (из-за санкций).

**Проверьте:**
- Работает ли `ping api.yookassa.ru`?
- Открывается ли `https://api.yookassa.ru/v3` в браузере на сервере?
- Если нет - обратитесь к провайдеру/хостингу

**Возможные решения:**
- Использование прокси-сервера (если доступен)
- Использование VPN (если разрешено политикой)
- Обращение к провайдеру для разблокировки доступа к YooKassa

#### Шаг 4: Альтернативные методы диагностики

**Через PowerShell:**
```powershell
# Проверка DNS
nslookup api.yookassa.ru

# Проверка TCP соединения
Test-NetConnection -ComputerName api.yookassa.ru -Port 443

# Проверка через IP адреса
Test-NetConnection -ComputerName 109.235.165.99 -Port 443
Test-NetConnection -ComputerName 185.71.78.133 -Port 443
```

**Через браузер:**
- Откройте `https://api.yookassa.ru/v3` в браузере на сервере
- Если не открывается - проблема в сетевой блокировке

### Диагностические скрипты

В папке `scripts/` доступны следующие скрипты для работы с YooKassa:

- **`test_yookassa_connection.bat`** — тестирование подключения к YooKassa API
- **`fix_yookassa_firewall.bat`** — настройка файрвола Windows для доступа к YooKassa (требует прав администратора)

## 🖥️ Информация о продакшн сервере

### Данные сервера

- **IP адрес:** 93.88.203.86
- **ОС:** Ubuntu 22.04 LTS
- **Расположение:** Россия
- **SSH доступ:**
  - Пользователь: `root`
  - Пароль: `n5nxGTZeFztJf`
  - Подключение: `ssh root@93.88.203.86`
- **Пользователь бота:** `gptbot`
- **Директория проекта:** `/opt/gptbot`

**Примечание:** На русском сервере прокси для YooKassa не требуется, так как сервер находится в России и имеет прямой доступ к YooKassa API.

### База данных

- **PostgreSQL 14**
- **Пользователь:** `app`
- **Пароль:** `app`
- **База данных:** `app`
- **Порт:** `5432`
- **Подключение:** `postgresql+psycopg://app:app@localhost:5432/app`

### Redis

- **Порт:** `6379`
- **Локальный сервер:** `redis://localhost:6379/0`

### Systemd сервисы

Бот и API работают как systemd сервисы:

- **`gptbot-api.service`** — API сервер (FastAPI)
- **`gptbot-bot.service`** — Telegram бот

**Управление сервисами:**

```bash
# Просмотр статуса
systemctl status gptbot-api.service
systemctl status gptbot-bot.service

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
journalctl -u gptbot-api.service -f
journalctl -u gptbot-bot.service -f

# Проверка автозапуска
systemctl is-enabled gptbot-api.service
systemctl is-enabled gptbot-bot.service
```

## 📋 Полный список переменных окружения

Все переменные настраиваются в файле `.env` на сервере (`/opt/gptbot/.env`):

### Основные настройки

- **`BOT_TOKEN`** — токен Telegram-бота (получить у [@BotFather](https://t.me/BotFather))
- **`OPENAI_API_KEY`** — ключ OpenAI API для работы с GPT моделями
- **`ADMIN_IDS`** — список Telegram ID администраторов через запятую или пробел (например: `356142844`)
- **`DATABASE_URL`** — строка подключения к PostgreSQL (формат: `postgresql+psycopg://user:password@host:port/database`)
- **`REDIS_URL`** — строка подключения к Redis (формат: `redis://host:port/db`)
- **`PUBLIC_BASE_URL`** — публичный URL API для вебхуков (например: `http://93.88.203.86:8000`)
- **`WEBHOOK_SECRET`** — секретный ключ для верификации webhook запросов

### Настройки платежей

- **`YOOKASSA_SHOP_ID`** — ID магазина в YooKassa
- **`YOOKASSA_SECRET_KEY`** — секретный ключ YooKassa (начинается с `live_` для продакшена)
- **`YOOKASSA_PROXY`** — прокси для доступа к YooKassa (на русском сервере не требуется, оставьте пустым)
- **`TELEGRAM_PAYMENT_TOKEN`** — токен провайдера Telegram Payments (от YooKassa, формат: `shop_id:LIVE:token`)

### Настройки прокси для OpenAI

- **`OPENAI_PROXY`** — прокси для доступа к OpenAI API (если нужен, формат: `http://host:port`, `socks5://host:port` или `http://user:pass@host:port`)
  - Используется для работы с GPT API, если OpenAI заблокирован
  - Поддерживаются HTTP, HTTPS и SOCKS5 прокси
  - Для SOCKS5 требуется установка `httpx-socks` (уже включен в requirements.txt)

### Настройки KLING-V2 API (оживление фото)

- **`KLING_ACCESS_KEY`** — Access Key для KLING-V2 API
- **`KLING_SECRET_KEY`** — Secret Key для KLING-V2 API
- **`KLING_API_ID`** — ID API (например: 55069011)
- **`KLING_API_BASE_URL`** — базовый URL API (по умолчанию: `https://api.klingai.com/v2`)

### Дополнительные настройки

- **`SENTRY_DSN`** — DSN для Sentry (мониторинг ошибок, опционально)
- **`LOG_LEVEL`** — уровень логирования (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

### Настройки биллинга (стоимость операций в токенах)

- **`BILLING_VISION_SURCHARGE`** — доплата за обработку фото в vision запросах (по умолчанию: 150)
- **`BILLING_STT_PER_MIN`** — стоимость расшифровки аудио за минуту (по умолчанию: 900)
- **`BILLING_TTS_PER_1K_CHARS`** — стоимость синтеза речи за 1000 символов (по умолчанию: 600)
- **`BILLING_FACESWAP_COST`** — стоимость замены лица (по умолчанию: 7500)
- **`BILLING_PHOTO_ENHANCE_COST`** — стоимость улучшения фото (по умолчанию: 4000)
- **`BILLING_PHOTO_REPLACE_BG_COST`** — стоимость замены фона (по умолчанию: 11000)
- **`BILLING_PHOTO_REMOVE_BG_COST`** — стоимость удаления фона (по умолчанию: 7500)
- **`BILLING_PHOTO_ANIMATE_COST`** — стоимость оживления фото через KLING-V2 (по умолчанию: 10)
- **`BILLING_GPT_IMAGE_COST`** — стоимость генерации изображения через GPT (по умолчанию: 9500)

## 🤖 Инструкции для следующей нейронки (AI ассистента)

### Что это за проект?

Это Telegram-бот на базе GPT-5, который предоставляет пользователям доступ к различным AI функциям:
- Чат с GPT моделями (текст и изображения)
- Генерация изображений через DALL-E
- Обработка фотографий (улучшение, замена фона, удаление фона)
- Замена лиц на фотографиях (FaceSwap)
- Работа с аудио (распознавание речи, синтез речи)
- Система подписок и платежей через YooKassa

### Архитектура системы

**Компоненты:**
1. **Telegram Bot** (`app/bot/`) — обработка команд и сообщений от пользователей
2. **FastAPI Server** (`app/api/`) — REST API для вебхуков и админки
3. **PostgreSQL** — основная база данных (пользователи, платежи, балансы)
4. **Redis** — кэширование и очереди
5. **OpenAI API** — интеграция с GPT моделями
6. **YooKassa** — обработка платежей

**Структура проекта:**
```
app/
├── bot/              # Telegram бот (Aiogram 3)
│   ├── handlers/     # Обработчики команд и сообщений
│   ├── keyboards/    # Клавиатуры для бота
│   └── utils/        # Утилиты бота
├── api/              # FastAPI сервер
│   └── main.py       # Основной файл API
├── db/               # Работа с базой данных
│   ├── models.py     # SQLAlchemy модели
│   ├── session.py    # Настройка сессий БД
│   └── migrations/   # Alembic миграции
├── services/         # Бизнес-логика
│   ├── billing.py   # Система биллинга и подписок
│   ├── payments.py  # Интеграция с YooKassa
│   ├── llm.py       # Работа с GPT моделями
│   ├── audio.py     # Работа с аудио
│   └── photo.py     # Обработка фотографий
└── config.py        # Настройки приложения
```

### Как обновлять код на сервере

**Важно:** Все изменения кода нужно применять на сервере Linux (93.88.203.86), а не на Windows машине разработчика.

**Процесс обновления:**

1. **Подключитесь к серверу по SSH:**
   ```bash
   ssh root@93.88.203.86
   # Пароль: n5nxGTZeFztJf
   ```

2. **Перейдите в директорию проекта:**
   ```bash
   cd /opt/gptbot
   ```

3. **Скопируйте обновленный код на сервер:**
   - Вариант 1: Через `scp` с локальной машины:
     ```bash
     # С локальной машины (Windows)
     scp -r app root@93.88.203.86:/opt/gptbot/
     ```
   - Вариант 2: Через `git` (если используется):
     ```bash
     # На сервере
     git pull origin main
     ```
   - Вариант 3: Вручную через SFTP клиент (FileZilla, WinSCP)

4. **Примените миграции БД (если есть изменения структуры):**
   ```bash
   cd /opt/gptbot
   source venv/bin/activate
   python -m alembic upgrade head
   ```

5. **Перезапустите сервисы:**
   ```bash
   systemctl restart gptbot-api.service
   systemctl restart gptbot-bot.service
   ```

6. **Проверьте статус:**
   ```bash
   systemctl status gptbot-api.service
   systemctl status gptbot-bot.service
   ```

7. **Проверьте логи на ошибки:**
   ```bash
   journalctl -u gptbot-api.service -n 50
   journalctl -u gptbot-bot.service -n 50
   ```

### Как перезапускать сервисы

**Перезапуск всех сервисов:**
```bash
systemctl restart gptbot-api.service gptbot-bot.service
```

**Перезапуск отдельного сервиса:**
```bash
# API
systemctl restart gptbot-api.service

# Bot
systemctl restart gptbot-bot.service
```

**Проверка статуса:**
```bash
systemctl status gptbot-api.service
systemctl status gptbot-bot.service
```

### Как проверять логи

**Просмотр логов в реальном времени:**
```bash
# API сервер
journalctl -u gptbot-api.service -f

# Telegram бот
journalctl -u gptbot-bot.service -f
```

**Просмотр последних N строк:**
```bash
# Последние 100 строк API
journalctl -u gptbot-api.service -n 100

# Последние 100 строк бота
journalctl -u gptbot-bot.service -n 100
```

**Поиск ошибок:**
```bash
# Поиск ошибок в логах API
journalctl -u gptbot-api.service | grep -i error

# Поиск ошибок в логах бота
journalctl -u gptbot-bot.service | grep -i error
```

### Как делать бэкапы БД

**Создание бэкапа:**
```bash
# На сервере
sudo -u postgres pg_dump -d app > /opt/gptbot/backup_$(date +%Y%m%d_%H%M%S).sql
```

**Восстановление из бэкапа:**
```bash
# Остановить сервисы перед восстановлением
systemctl stop gptbot-api.service gptbot-bot.service

# Восстановить БД
sudo -u postgres psql -d app < /opt/gptbot/backup_YYYYMMDD_HHMMSS.sql

# Запустить сервисы
systemctl start gptbot-api.service gptbot-bot.service
```

### Важные файлы и их назначение

- **`/opt/gptbot/.env`** — файл с переменными окружения (пароли, токены, настройки)
- **`/opt/gptbot/app/`** — исходный код приложения
- **`/opt/gptbot/venv/`** — виртуальное окружение Python с зависимостями
- **`/etc/systemd/system/gptbot-api.service`** — конфигурация systemd сервиса API
- **`/etc/systemd/system/gptbot-bot.service`** — конфигурация systemd сервиса бота
- **`/opt/gptbot/alembic.ini`** — конфигурация Alembic (миграции БД)
- **`/opt/gptbot/app/db/migrations/`** — файлы миграций базы данных

### Процесс деплоя новых изменений

**Полный процесс обновления:**

1. **Подготовка на локальной машине:**
   - Внесите изменения в код
   - Протестируйте локально (если возможно)
   - Создайте миграции БД (если нужно): `python -m alembic revision --autogenerate -m "описание изменений"`

2. **Копирование на сервер:**
   ```bash
   # С локальной машины
   scp -r app root@149.33.0.41:/opt/gptbot/
   scp alembic.ini root@149.33.0.41:/opt/gptbot/
   scp -r app/db/migrations root@149.33.0.41:/opt/gptbot/app/db/
   ```

3. **На сервере - применение изменений:**
   ```bash
   ssh root@93.88.203.86
   cd /opt/gptbot
   
   # Активировать виртуальное окружение
   source venv/bin/activate
   
   # Применить миграции (если есть)
   python -m alembic upgrade head
   
   # Перезапустить сервисы
   systemctl restart gptbot-api.service gptbot-bot.service
   
   # Проверить статус
   systemctl status gptbot-api.service
   systemctl status gptbot-bot.service
   ```

4. **Проверка работоспособности:**
   ```bash
   # Проверить API
   curl http://localhost:8000/health
   # Должен вернуть: {"status":"ok"}
   
   # Проверить логи
   journalctl -u gptbot-api.service -n 20
   journalctl -u gptbot-bot.service -n 20
   ```

5. **Тестирование в боте:**
   - Откройте бота в Telegram
   - Отправьте `/start`
   - Проверьте основные функции

### Частые проблемы и решения

**Сервис не запускается:**
- Проверьте логи: `journalctl -u gptbot-api.service -n 50`
- Проверьте `.env` файл на наличие всех необходимых переменных
- Убедитесь что PostgreSQL и Redis запущены

**Ошибки подключения к БД:**
- Проверьте что PostgreSQL запущен: `systemctl status postgresql`
- Проверьте `DATABASE_URL` в `.env`
- Проверьте права пользователя `app` в PostgreSQL

**Ошибки при миграциях:**
- Убедитесь что пользователь БД имеет права на изменение структуры
- См. раздел "Решение проблемы с правами доступа при миграциях" выше

**Бот не отвечает:**
- Проверьте логи: `journalctl -u gptbot-bot.service -f`
- Проверьте `BOT_TOKEN` в `.env`
- Убедитесь что сервис запущен: `systemctl status gptbot-bot.service`


