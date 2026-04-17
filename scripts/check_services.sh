#!/bin/bash
# Скрипт проверки доступности YooKassa и OpenAI API
# Выполнять: bash check_services.sh

set -e

echo "=========================================="
echo "  Проверка доступности сервисов"
echo "=========================================="
echo

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

success() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ==========================================
# Проверка YooKassa API
# ==========================================
echo "Проверка YooKassa API (api.yookassa.ru)..."
echo

# DNS резолюция
echo -n "  DNS резолюция: "
if host api.yookassa.ru > /dev/null 2>&1; then
    IP=$(host api.yookassa.ru | grep "has address" | head -1 | awk '{print $4}')
    success "OK ($IP)"
else
    fail "FAILED"
fi

# Ping
echo -n "  Ping: "
if ping -c 2 api.yookassa.ru > /dev/null 2>&1; then
    success "OK"
else
    warn "TIMEOUT (может быть нормально, если ping заблокирован)"
fi

# TCP соединение на порт 443
echo -n "  TCP соединение (443): "
if timeout 5 bash -c "echo > /dev/tcp/api.yookassa.ru/443" 2>/dev/null; then
    success "OK"
else
    fail "FAILED"
fi

# HTTPS запрос
echo -n "  HTTPS запрос: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 https://api.yookassa.ru/v3 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ] || [ "$HTTP_CODE" = "404" ]; then
    success "OK (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "000" ]; then
    fail "FAILED (таймаут или ошибка подключения)"
else
    warn "HTTP $HTTP_CODE (сервер отвечает, но статус нестандартный)"
fi

echo

# ==========================================
# Проверка OpenAI API
# ==========================================
echo "Проверка OpenAI API (api.openai.com)..."
echo

# DNS резолюция
echo -n "  DNS резолюция: "
if host api.openai.com > /dev/null 2>&1; then
    IP=$(host api.openai.com | grep "has address" | head -1 | awk '{print $4}')
    success "OK ($IP)"
else
    fail "FAILED"
fi

# Ping
echo -n "  Ping: "
if ping -c 2 api.openai.com > /dev/null 2>&1; then
    success "OK"
else
    warn "TIMEOUT (может быть нормально, если ping заблокирован)"
fi

# TCP соединение на порт 443
echo -n "  TCP соединение (443): "
if timeout 5 bash -c "echo > /dev/tcp/api.openai.com/443" 2>/dev/null; then
    success "OK"
else
    fail "FAILED"
fi

# HTTPS запрос
echo -n "  HTTPS запрос: "
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 10 https://api.openai.com/v1/models 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "401" ]; then
    success "OK (HTTP $HTTP_CODE)"
elif [ "$HTTP_CODE" = "000" ]; then
    fail "FAILED (таймаут или ошибка подключения)"
else
    warn "HTTP $HTTP_CODE (сервер отвечает, но статус нестандартный)"
fi

echo

# ==========================================
# Проверка локальных сервисов
# ==========================================
echo "Проверка локальных сервисов..."
echo

# PostgreSQL
echo -n "  PostgreSQL: "
if systemctl is-active --quiet postgresql && sudo -u postgres psql -c "SELECT 1;" > /dev/null 2>&1; then
    success "OK"
else
    fail "FAILED"
fi

# Redis
echo -n "  Redis: "
if systemctl is-active --quiet redis-server && redis-cli ping > /dev/null 2>&1; then
    success "OK"
else
    fail "FAILED"
fi

echo
echo "=========================================="
echo "  Проверка завершена"
echo "=========================================="

