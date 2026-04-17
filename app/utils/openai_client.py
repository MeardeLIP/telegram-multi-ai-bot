"""
Утилита для создания OpenAI клиента с поддержкой прокси.
"""
import os
import httpx
from typing import Optional
from loguru import logger
from app.config import get_settings

# Поддержка SOCKS5 прокси
try:
    from httpx_socks import SyncProxyTransport
    SOCKS5_SUPPORT = True
except ImportError:
    SyncProxyTransport = None
    SOCKS5_SUPPORT = False


def create_openai_client() -> httpx.Client:
    """
    Создает httpx.Client для OpenAI с поддержкой прокси.
    
    Returns:
        httpx.Client: HTTP клиент с настроенным прокси (если указан)
    """
    settings = get_settings()
    
    # Проверяем настройки прокси в порядке приоритета
    proxy_url = None
    proxy_source = None
    
    if getattr(settings, "openai_proxy", "") and settings.openai_proxy.strip():
        proxy_url = settings.openai_proxy.strip()
        proxy_source = "settings.openai_proxy"
    elif os.getenv("OPENAI_PROXY", "").strip():
        proxy_url = os.getenv("OPENAI_PROXY", "").strip()
        proxy_source = "env.OPENAI_PROXY"
    elif os.getenv("HTTPS_PROXY", "").strip():
        proxy_url = os.getenv("HTTPS_PROXY", "").strip()
        proxy_source = "env.HTTPS_PROXY"
    elif os.getenv("HTTP_PROXY", "").strip():
        proxy_url = os.getenv("HTTP_PROXY", "").strip()
        proxy_source = "env.HTTP_PROXY"
    
    if not proxy_url:
        logger.debug("Прокси для OpenAI не настроен, используется прямое подключение")
        return httpx.Client(timeout=60.0)
    
    # Маскируем пароль в логах для безопасности
    masked_proxy = proxy_url
    if "@" in proxy_url:
        parts = proxy_url.split("@")
        if len(parts) == 2:
            auth_part = parts[0]
            scheme = ""
            if "://" in auth_part:
                scheme_parts = auth_part.split("://", 1)
                scheme = scheme_parts[0] + "://"
                auth_part = scheme_parts[1]
            if ":" in auth_part:
                user_pass = auth_part.split(":", 1)
                if len(user_pass) == 2:
                    masked_proxy = f"{scheme}{user_pass[0]}:****@{parts[1]}"
    
    logger.info(f"✅ ИСПОЛЬЗУЕТСЯ ПРОКСИ для OpenAI: {masked_proxy} (источник: {proxy_source})")
    
    try:
        if proxy_url.startswith("socks5://"):
            if not SOCKS5_SUPPORT:
                logger.error("❌ SOCKS5 прокси требует httpx-socks. Установите: pip install httpx-socks")
                logger.warning("⚠️ Используется прямое подключение без прокси")
                return httpx.Client(timeout=60.0)
            
            logger.info("🔍 Используется SOCKS5 транспорт для OpenAI")
            transport = SyncProxyTransport.from_url(proxy_url)
            return httpx.Client(transport=transport, timeout=60.0)
        else:
            logger.info("🔍 Используется HTTP/HTTPS прокси транспорт для OpenAI")
            return httpx.Client(proxy=proxy_url, timeout=60.0, verify=False)
    except Exception as e:
        logger.error(f"❌ ОШИБКА создания HTTP клиента с прокси для OpenAI: {e}")
        logger.warning("⚠️ Используется прямое подключение без прокси")
        return httpx.Client(timeout=60.0)

