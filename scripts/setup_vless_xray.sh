#!/usr/bin/env bash

# Настройка VLESS-прокси через Xray на сервере для использования в YooKassa.
# Поднимает локальный SOCKS5-прокси на 127.0.0.1:1080 и прописывает его в .env как YOOKASSA_PROXY.

set -euo pipefail

VLESS_ADDRESS="144.124.236.226"
VLESS_PORT=8443
VLESS_ID="OutlineUp_4219513"
VLESS_FLOW="xtls-rprx-vision"
REALITY_SERVER_NAME="sun6-21.userapi.com"
REALITY_PUBLIC_KEY="yn0UDqPE8E-SSOjBCScxt8Xjof4HoKmTpZ0plEElM3Y"
REALITY_SHORT_ID="ffffffffff"
REALITY_SPIDER_X="/"

GPTBOT_DIR="/opt/gptbot"
XRAY_CONFIG_DIR="/usr/local/etc/xray"
XRAY_CONFIG_PATH="${XRAY_CONFIG_DIR}/config.json"

echo "🚀 Настройка VLESS-прокси через Xray..."

if ! command -v xray >/dev/null 2>&1; then
  echo "📦 Xray не найден, устанавливаю..."
  bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" >/tmp/xray-install.log 2>&1 || {
    echo "✗ Не удалось установить Xray. Лог в /tmp/xray-install.log"
    exit 1
  }
else
  echo "✓ Xray уже установлен"
fi

mkdir -p "${XRAY_CONFIG_DIR}"

echo "📝 Обновление конфигурации Xray в ${XRAY_CONFIG_PATH}"
cat > "${XRAY_CONFIG_PATH}" <<EOF
{
  "log": {
    "loglevel": "info"
  },
  "inbounds": [
    {
      "tag": "socks-in",
      "port": 1080,
      "listen": "127.0.0.1",
      "protocol": "socks",
      "settings": {
        "udp": true,
        "auth": "noauth"
      }
    }
  ],
  "outbounds": [
    {
      "tag": "vless-out",
      "protocol": "vless",
      "settings": {
        "vnext": [
          {
            "address": "${VLESS_ADDRESS}",
            "port": ${VLESS_PORT},
            "users": [
              {
                "id": "${VLESS_ID}",
                "encryption": "none",
                "flow": "${VLESS_FLOW}"
              }
            ]
          }
        ]
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "serverName": "${REALITY_SERVER_NAME}",
          "publicKey": "${REALITY_PUBLIC_KEY}",
          "shortId": "${REALITY_SHORT_ID}",
          "spiderX": "${REALITY_SPIDER_X}"
        }
      }
    }
  ],
  "routing": {
    "domainStrategy": "AsIs",
    "rules": [
      {
        "type": "field",
        "outboundTag": "vless-out",
        "network": "tcp,udp"
      }
    ]
  }
}
EOF

echo "🔄 Перезапуск Xray..."
systemctl restart xray || {
  echo "✗ Не удалось перезапустить xray.service"
  systemctl status xray --no-pager -l || true
  exit 1
}

sleep 2
systemctl status xray --no-pager -l | head -n 20 || true

ENV_PATH="${GPTBOT_DIR}/.env"
echo "📝 Обновление YOOKASSA_PROXY в ${ENV_PATH}"

if [ -f "${ENV_PATH}" ]; then
  if grep -q '^YOOKASSA_PROXY=' "${ENV_PATH}"; then
    sed -i 's|^YOOKASSA_PROXY=.*|YOOKASSA_PROXY=socks5://127.0.0.1:1080|' "${ENV_PATH}"
  else
    echo 'YOOKASSA_PROXY=socks5://127.0.0.1:1080' >> "${ENV_PATH}"
  fi
else
  echo "⚠ .env не найден, создаю новый"
  echo 'YOOKASSA_PROXY=socks5://127.0.0.1:1080' > "${ENV_PATH}"
fi

echo "🔄 Перезапуск сервисов gptbot..."
systemctl restart gptbot-api.service gptbot-bot.service || {
  echo "✗ Не удалось перезапустить gptbot-api/bot"
  systemctl status gptbot-api.service --no-pager -l || true
  systemctl status gptbot-bot.service --no-pager -l || true
  exit 1
}

echo "✅ VLESS-прокси через Xray настроен. YooKassa будет использовать socks5://127.0.0.1:1080"


