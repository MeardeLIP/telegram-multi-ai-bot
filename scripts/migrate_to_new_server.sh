#!/bin/bash
# Скрипт для переноса базы данных на новый сервер
# Использование: 
#   На старом сервере: bash migrate_to_new_server.sh backup
#   На новом сервере: bash migrate_to_new_server.sh restore <backup_file>

set -e

OLD_SERVER_IP="149.33.0.41"
OLD_SERVER_USER="root"
NEW_SERVER_IP="93.88.203.86"
NEW_SERVER_USER="root"
DB_NAME="app"
DB_USER="app"
DB_PASSWORD="app"
BACKUP_DIR="/opt/gptbot/backups"
BACKUP_FILE="${BACKUP_DIR}/migration_backup_$(date +%Y%m%d_%H%M%S).sql"

case "$1" in
    backup)
        echo "📦 Создание бэкапа базы данных на старом сервере..."
        
        # Создаем директорию для бэкапов
        mkdir -p "$BACKUP_DIR"
        
        # Создаем бэкап
        echo "Создание бэкапа в $BACKUP_FILE..."
        sudo -u postgres pg_dump -d "$DB_NAME" > "$BACKUP_FILE"
        
        if [ $? -eq 0 ]; then
            echo "✅ Бэкап создан успешно: $BACKUP_FILE"
            echo ""
            echo "Размер файла: $(du -h "$BACKUP_FILE" | cut -f1)"
            echo ""
            echo "Следующие шаги:"
            echo "1. Скопируйте файл на новый сервер:"
            echo "   scp $BACKUP_FILE ${NEW_SERVER_USER}@${NEW_SERVER_IP}:/opt/gptbot/backups/"
            echo ""
            echo "2. На новом сервере выполните:"
            echo "   bash migrate_to_new_server.sh restore $(basename $BACKUP_FILE)"
        else
            echo "❌ Ошибка при создании бэкапа"
            exit 1
        fi
        ;;
    
    restore)
        if [ -z "$2" ]; then
            echo "❌ Ошибка: укажите имя файла бэкапа"
            echo "Использование: bash migrate_to_new_server.sh restore <backup_file>"
            exit 1
        fi
        
        BACKUP_FILE_PATH="${BACKUP_DIR}/$2"
        
        if [ ! -f "$BACKUP_FILE_PATH" ]; then
            echo "❌ Ошибка: файл бэкапа не найден: $BACKUP_FILE_PATH"
            exit 1
        fi
        
        echo "📥 Восстановление базы данных из бэкапа..."
        echo "Файл: $BACKUP_FILE_PATH"
        
        # Останавливаем сервисы перед восстановлением
        echo ""
        echo "⏸️ Остановка сервисов..."
        systemctl stop gptbot-api.service gptbot-bot.service 2>/dev/null || true
        
        # Восстанавливаем БД
        echo ""
        echo "📥 Восстановление базы данных..."
        sudo -u postgres psql -d "$DB_NAME" < "$BACKUP_FILE_PATH"
        
        if [ $? -eq 0 ]; then
            echo "✅ База данных восстановлена успешно"
            
            # Применяем миграции (на случай если структура изменилась)
            echo ""
            echo "🔄 Применение миграций..."
            cd /opt/gptbot
            source venv/bin/activate
            python -m alembic upgrade head
            
            # Запускаем сервисы
            echo ""
            echo "▶️ Запуск сервисов..."
            systemctl start gptbot-api.service gptbot-bot.service
            
            echo ""
            echo "✅ Миграция завершена успешно!"
        else
            echo "❌ Ошибка при восстановлении базы данных"
            exit 1
        fi
        ;;
    
    *)
        echo "Использование:"
        echo "  На старом сервере: bash migrate_to_new_server.sh backup"
        echo "  На новом сервере: bash migrate_to_new_server.sh restore <backup_file>"
        exit 1
        ;;
esac

