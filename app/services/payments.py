from typing import Any, Optional
from uuid import uuid4
import logging
import socket
import ssl
import asyncio
import os

import httpx

# Поддержка SOCKS5 прокси
try:
    from httpx_socks import AsyncProxyTransport
    SOCKS5_SUPPORT = True
    SOCKS5_VERSION = None
    try:
        import httpx_socks
        SOCKS5_VERSION = getattr(httpx_socks, '__version__', 'unknown')
    except:
        pass
except ImportError:
    AsyncProxyTransport = None
    SOCKS5_SUPPORT = False
    SOCKS5_VERSION = None

from app.config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)

# Логируем статус поддержки SOCKS5 при загрузке модуля
if SOCKS5_SUPPORT:
    logger.info(f"✅ httpx-socks установлен (версия: {SOCKS5_VERSION or 'unknown'}), SOCKS5 прокси поддерживается")
else:
    logger.warning("⚠️ httpx-socks НЕ установлен, SOCKS5 прокси не будет работать")
    logger.warning("   Для использования SOCKS5 прокси установите: pip install httpx-socks")


async def test_yookassa_connection() -> dict:
	"""
	Диагностическая функция для проверки доступности YooKassa API.
	Проверяет DNS, TCP соединение и HTTPS доступность.
	"""
	api_host = "api.yookassa.ru"
	api_port = 443
	results = {
		"dns_resolution": {"status": "unknown", "ips": [], "error": None},
		"tcp_connection": {"status": "unknown", "error": None},
		"ssl_handshake": {"status": "unknown", "error": None},
		"https_request": {"status": "unknown", "status_code": None, "error": None},
	}
	
	# 1. Проверка DNS
	logger.info(f"Диагностика: Проверка DNS для {api_host}")
	try:
		ips = socket.gethostbyname_ex(api_host)[2]
		results["dns_resolution"]["status"] = "success"
		results["dns_resolution"]["ips"] = ips
		logger.info(f"Диагностика: DNS разрешен в IP: {ips}")
	except Exception as e:
		results["dns_resolution"]["status"] = "failed"
		results["dns_resolution"]["error"] = str(e)
		logger.error(f"Диагностика: Ошибка DNS: {e}")
	
	# 2. Проверка TCP соединения (в отдельном потоке, чтобы не блокировать event loop)
	logger.info(f"Диагностика: Проверка TCP соединения к {api_host}:{api_port}")
	try:
		def check_tcp():
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			sock.settimeout(10)
			result = sock.connect_ex((api_host, api_port))
			sock.close()
			return result
		
		result = await asyncio.to_thread(check_tcp)
		if result == 0:
			results["tcp_connection"]["status"] = "success"
			logger.info(f"Диагностика: TCP соединение успешно")
		else:
			results["tcp_connection"]["status"] = "failed"
			results["tcp_connection"]["error"] = f"Connection refused (error code: {result})"
			logger.error(f"Диагностика: TCP соединение не удалось: {result}")
	except Exception as e:
		results["tcp_connection"]["status"] = "failed"
		results["tcp_connection"]["error"] = str(e)
		logger.error(f"Диагностика: Ошибка TCP соединения: {e}")
	
	# 3. Проверка SSL handshake (в отдельном потоке)
	logger.info(f"Диагностика: Проверка SSL handshake с {api_host}:{api_port}")
	try:
		def check_ssl():
			context = ssl.create_default_context()
			with socket.create_connection((api_host, api_port), timeout=10) as sock:
				with context.wrap_socket(sock, server_hostname=api_host) as ssock:
					cert = ssock.getpeercert()
					return cert
		
		cert = await asyncio.to_thread(check_ssl)
		results["ssl_handshake"]["status"] = "success"
		logger.info(f"Диагностика: SSL handshake успешен, сертификат: {cert.get('subject', {})}")
	except Exception as e:
		results["ssl_handshake"]["status"] = "failed"
		results["ssl_handshake"]["error"] = str(e)
		logger.error(f"Диагностика: Ошибка SSL handshake: {e}")
	
	# 4. Проверка HTTPS запроса
	logger.info(f"Диагностика: Проверка HTTPS запроса к {api_host}")
	try:
		# Используем прокси если настроен
		proxy_url = None
		proxy_source = None
		
		if getattr(settings, 'yookassa_proxy', '') and settings.yookassa_proxy:
			proxy_url = settings.yookassa_proxy
			proxy_source = "settings.yookassa_proxy"
		elif os.getenv("YOOKASSA_PROXY"):
			proxy_url = os.getenv("YOOKASSA_PROXY")
			proxy_source = "env.YOOKASSA_PROXY"
		elif os.getenv("HTTPS_PROXY"):
			proxy_url = os.getenv("HTTPS_PROXY")
			proxy_source = "env.HTTPS_PROXY"
		elif os.getenv("HTTP_PROXY"):
			proxy_url = os.getenv("HTTP_PROXY")
			proxy_source = "env.HTTP_PROXY"
		
		client_kwargs = {"timeout": 30.0}
		if proxy_url:
			# Маскируем пароль в логах для безопасности
			masked_proxy = proxy_url
			if "@" in proxy_url:
				parts = proxy_url.split("@")
				if len(parts) == 2:
					auth_part = parts[0]
					if ":" in auth_part:
						user_pass = auth_part.split(":", 1)
						if len(user_pass) == 2:
							masked_proxy = f"{user_pass[0]}:****@{parts[1]}"
			
			logger.info(f"Диагностика: Используется прокси: {masked_proxy} (источник: {proxy_source})")
			
			# Для SOCKS5 используем специальный транспорт
			if proxy_url.startswith("socks5://"):
				if SOCKS5_SUPPORT:
					transport = AsyncProxyTransport.from_url(proxy_url)
					logger.info("Диагностика: Используется SOCKS5 транспорт")
				else:
					logger.warning("Диагностика: SOCKS5 требует httpx-socks, используем HTTP транспорт")
					transport = httpx.AsyncHTTPTransport(proxy=proxy_url, verify=False)
			else:
				transport = httpx.AsyncHTTPTransport(proxy=proxy_url, verify=False)
			client_kwargs["transport"] = transport
		else:
			logger.info("Диагностика: Прокси не настроен, используется прямое подключение")
		
		async with httpx.AsyncClient(**client_kwargs) as client:
			response = await client.get(f"https://{api_host}/v3", follow_redirects=True)
			results["https_request"]["status"] = "success"
			results["https_request"]["status_code"] = response.status_code
			logger.info(f"Диагностика: HTTPS запрос успешен, статус: {response.status_code}")
	except httpx.ConnectError as e:
		results["https_request"]["status"] = "failed"
		results["https_request"]["error"] = f"ConnectError: {str(e)}"
		logger.error(f"Диагностика: Ошибка подключения HTTPS: {e}")
	except httpx.TimeoutException as e:
		results["https_request"]["status"] = "failed"
		results["https_request"]["error"] = f"TimeoutException: {str(e)}"
		logger.error(f"Диагностика: Таймаут HTTPS запроса: {e}")
	except Exception as e:
		results["https_request"]["status"] = "failed"
		results["https_request"]["error"] = f"{type(e).__name__}: {str(e)}"
		logger.error(f"Диагностика: Неожиданная ошибка HTTPS: {e}")
	
	return results


class YooKassaGateway:
	API_BASE_URL = "https://api.yookassa.ru/v3"

	def __init__(self) -> None:
		self.shop_id = settings.yookassa_shop_id
		self.secret = settings.yookassa_secret_key

	async def create_invoice(
		self,
		amount_rub: int,
		description: str,
		return_url: str,
		metadata: Optional[dict[str, Any]] = None,
		customer_email: Optional[str] = None,
		customer_phone: Optional[str] = None,
	) -> dict:
		"""
		Создает платеж в YooKassa с поддержкой чеков для самозанятых.
		
		Args:
			amount_rub: Сумма платежа в рублях
			description: Описание платежа
			return_url: URL для возврата после оплаты
			metadata: Дополнительные метаданные
			customer_email: Email покупателя (для чека)
			customer_phone: Телефон покупателя (для чека, формат: +79001234567)
		"""
		if not self.shop_id or not self.secret:
			raise RuntimeError("ЮKassa credentials are not configured")

		payload = {
			"amount": {"value": f"{amount_rub:.2f}", "currency": "RUB"},
			"capture": True,
			"confirmation": {"type": "redirect", "return_url": return_url},
			"description": description[:128],
		}
		if metadata:
			payload["metadata"] = metadata
		
		# Добавляем receipt для отправки чека в налоговую (для самозанятых)
		receipt = {
			"customer": {},
			"items": [
				{
					"description": description[:128],
					"quantity": "1.00",
					"amount": {
						"value": f"{amount_rub:.2f}",
						"currency": "RUB"
					},
					"vat_code": 1  # Без НДС (для самозанятых)
				}
			]
		}
		
		# Указываем email или телефон покупателя (обязательно для чека)
		if customer_email:
			receipt["customer"]["email"] = customer_email
		elif customer_phone:
			receipt["customer"]["phone"] = customer_phone
		else:
			# Если нет email и телефона, используем формат с tg_id из metadata
			# Это fallback, но лучше передавать email или телефон
			if metadata and "user_id" in metadata:
				# Используем формат, который YooKassa примет, но лучше передавать реальный email
				receipt["customer"]["email"] = f"user_{metadata['user_id']}@telegram.local"
				logger.warning(f"⚠️ Используется fallback email для чека: user_{metadata['user_id']}@telegram.local")
			else:
				# Если нет даже user_id, используем общий формат
				receipt["customer"]["email"] = "customer@telegram.local"
				logger.warning("⚠️ Используется общий fallback email для чека")
		
		payload["receipt"] = receipt

		headers = {"Idempotence-Key": str(uuid4())}
		url = f"{self.API_BASE_URL}/payments"

		logger.info(f"Создание платежа в YooKassa: amount={amount_rub}, url={url}")
		logger.debug(f"Детали запроса: shop_id={self.shop_id[:10]}..., payload={payload}")

		# Настройка прокси для YooKassa (если указан).
		# Приоритет: settings.yookassa_proxy -> переменные окружения -> без прокси.
		proxy_url = None
		proxy_source = None
		
		# Проверяем настройки в порядке приоритета
		if getattr(settings, "yookassa_proxy", "") and settings.yookassa_proxy.strip():
			proxy_url = settings.yookassa_proxy.strip()
			proxy_source = "settings.yookassa_proxy"
		elif os.getenv("YOOKASSA_PROXY", "").strip():
			proxy_url = os.getenv("YOOKASSA_PROXY", "").strip()
			proxy_source = "env.YOOKASSA_PROXY"
		elif os.getenv("HTTPS_PROXY", "").strip():
			proxy_url = os.getenv("HTTPS_PROXY", "").strip()
			proxy_source = "env.HTTPS_PROXY"
		elif os.getenv("HTTP_PROXY", "").strip():
			proxy_url = os.getenv("HTTP_PROXY", "").strip()
			proxy_source = "env.HTTP_PROXY"

		transport: Optional[httpx.AsyncHTTPTransport] = None
		masked_proxy = None  # Для использования в логах позже
		if proxy_url:
			# Маскируем пароль в логах для безопасности, сохраняя схему
			masked_proxy = proxy_url
			if "@" in proxy_url:
				parts = proxy_url.split("@")
				if len(parts) == 2:
					auth_part = parts[0]
					# Извлекаем схему (если есть)
					scheme = ""
					if "://" in auth_part:
						scheme_parts = auth_part.split("://", 1)
						scheme = scheme_parts[0] + "://"
						auth_part = scheme_parts[1]
					if ":" in auth_part:
						user_pass = auth_part.split(":", 1)
						if len(user_pass) == 2:
							masked_proxy = f"{scheme}{user_pass[0]}:****@{parts[1]}"
			
			logger.info(
				f"✅ ИСПОЛЬЗУЕТСЯ ПРОКСИ для YooKassa: {masked_proxy} "
				f"(источник: {proxy_source})"
			)
			proxy_scheme = proxy_url.split("://")[0] if "://" in proxy_url else "unknown"
			logger.info(f"🔍 Детали прокси: схема={proxy_scheme}")
			
			# Проверяем формат прокси
			if not proxy_url.startswith(("http://", "https://", "socks5://", "socks4://")):
				logger.warning(f"⚠️ Неподдерживаемая схема прокси: {proxy_scheme}, попробуем использовать как есть")
			
			# Для SOCKS5 используем специальный транспорт
			try:
				if proxy_url.startswith("socks5://"):
					if not SOCKS5_SUPPORT:
						logger.error("❌ SOCKS5 прокси требует httpx-socks. Установите: pip install httpx-socks")
						logger.error(f"❌ Прокси URL: {masked_proxy}")
						raise RuntimeError(
							"SOCKS5 прокси требует httpx-socks библиотеку. "
							"Установите: pip install httpx-socks"
						)
					
					logger.info(f"🔍 Используется SOCKS5 транспорт (httpx-socks версия: {SOCKS5_VERSION or 'unknown'})")
					logger.info(f"🔍 Прокси URL: {masked_proxy}")
					transport = AsyncProxyTransport.from_url(proxy_url)
					logger.info("✅ SOCKS5 Transport создан успешно")
				else:
					# httpx поддерживает прокси в формате http://user:pass@host:port
					# Для HTTPS запросов через HTTP прокси httpx автоматически использует CONNECT метод
					logger.info("🔍 Используется HTTP/HTTPS прокси транспорт")
					transport = httpx.AsyncHTTPTransport(
						proxy=proxy_url,
						verify=False,  # многие прокси не умеют нормально работать с SSL‑верификацией
					)
					logger.info("✅ HTTP Transport с прокси создан успешно")
			except Exception as e:
				logger.error(f"❌ ОШИБКА создания transport с прокси: {e}")
				logger.error(f"❌ Прокси URL: {masked_proxy}")
				raise RuntimeError(f"Не удалось создать transport с прокси: {e}") from e
		else:
			logger.warning(
				"⚠️ Прокси для YooKassa НЕ НАЙДЕН, используется прямое подключение. "
				"Проверены: settings.yookassa_proxy, env.YOOKASSA_PROXY, env.HTTPS_PROXY, env.HTTP_PROXY"
			)
			logger.warning("⚠️ Это может привести к таймаутам, если YooKassa заблокирован!")

		# Увеличиваем таймаут если используется прокси (прокси может быть медленнее)
		client_timeout = 30.0 if proxy_url else 15.0
		max_attempts = 3

		last_error: Exception | None = None

		for attempt in range(1, max_attempts + 1):
			try:
				proxy_status = "ON" if proxy_url else "OFF"
				logger.info(
					f"🔄 Попытка #{attempt}/{max_attempts} отправки запроса в YooKassa "
					f"(timeout={client_timeout}s, proxy={proxy_status})"
				)
				if proxy_url and masked_proxy:
					logger.info(f"🔍 Прокси будет использован: {masked_proxy}")
				async with httpx.AsyncClient(timeout=client_timeout, transport=transport) as client:
					logger.info(f"📤 Отправка POST запроса к {url}")
					if proxy_url:
						logger.info(f"🔍 Запрос идет через прокси: {masked_proxy}")
					response = await client.post(
						url,
						json=payload,
						auth=(self.shop_id, self.secret),
						headers=headers,
					)
				logger.info(f"📥 Ответ YooKassa получен: status={response.status_code}")
				logger.debug(f"Заголовки ответа: {dict(response.headers)}")

				try:
					response.raise_for_status()
				except httpx.HTTPStatusError as exc:
					text = exc.response.text
					logger.error(f"YooKassa API вернул ошибку: status={exc.response.status_code}, text={text}")
					
					# Проверяем, является ли это ошибкой "Receipt is missing"
					if exc.response.status_code == 400 and ("Receipt is missing" in text or "receipt" in text.lower()):
						logger.error("⚠️ YooKassa требует receipt (чек). Отключите требование чека в настройках магазина YooKassa.")
					
					raise RuntimeError(f"YooKassa API error (status {exc.response.status_code}): {text}") from exc

				result = response.json()
				logger.info(f"Платеж успешно создан в YooKassa: payment_id={result.get('id')}")
				return result

			except httpx.TimeoutException as exc:
				last_error = exc
				proxy_info = f" (через прокси: {masked_proxy})" if proxy_url and masked_proxy else " (без прокси)"
				error_str = str(exc)
				logger.error(
					f"⏱️ ТАЙМАУТ при подключении к YooKassa API{proxy_info} "
					f"(попытка {attempt}/{max_attempts}, timeout={client_timeout}s)"
				)
				logger.error(f"⏱️ Детали ошибки: {error_str}")
				
				if proxy_url:
					logger.error(f"⚠️ ДИАГНОСТИКА ТАЙМАУТА:")
					logger.error(f"   Прокси: {masked_proxy}")
					logger.error(f"   Таймаут установлен: {client_timeout}s")
					logger.error(f"   ⚠️ ВОЗМОЖНЫЕ ПРИЧИНЫ:")
					logger.error(f"   1) Прокси слишком медленный (ответ > {client_timeout}s)")
					logger.error(f"   2) Прокси перегружен или недоступен")
					logger.error(f"   3) Проблемы с сетью между сервером и прокси")
					logger.error(f"   4) YooKassa API недоступен через прокси")
				
				if attempt < max_attempts:
					# Небольшая задержка перед повтором
					await asyncio.sleep(1.0)
					continue
				error_msg = f"Таймаут при подключении к YooKassa API. Попыток: {max_attempts}, timeout={client_timeout}s."
				if proxy_url:
					error_msg += f" Прокси: {masked_proxy}. Прокси может быть недоступен или слишком медленный."
				raise RuntimeError(error_msg) from exc

			except Exception as exc:
				# Проверяем, является ли это ProxyError от python_socks
				error_type = type(exc).__name__
				error_str = str(exc)
				
				# ProxyError от python_socks (используется httpx-socks)
				# Также проверяем специфичные сообщения об ошибках прокси
				is_proxy_error = (
					"ProxyError" in error_type or 
					"proxy" in error_str.lower() or
					"Connection refused by destination host" in error_str or
					"destination host" in error_str.lower()
				)
				
				if is_proxy_error:
					last_error = exc
					proxy_info = f" (через прокси: {masked_proxy})" if proxy_url and masked_proxy else " (без прокси)"
					logger.error(
						f"🔌 ОШИБКА ПРОКСИ при подключении к YooKassa API{proxy_info} "
						f"(попытка {attempt}/{max_attempts})"
					)
					logger.error(f"🔌 Тип ошибки: {error_type}")
					logger.error(f"🔌 Детали ошибки: {error_str}")
					
					if proxy_url:
						proxy_host_port = "unknown"
						if "@" in proxy_url:
							proxy_host_port = proxy_url.split("@")[1]
						elif "://" in proxy_url:
							proxy_host_port = proxy_url.split("://")[1]
							if "@" in proxy_host_port:
								proxy_host_port = proxy_host_port.split("@")[1]
						
						logger.error(f"⚠️ ДИАГНОСТИКА ПРОКСИ:")
						logger.error(f"   Прокси: {masked_proxy}")
						logger.error(f"   Хост:порт: {proxy_host_port}")
						logger.error(f"   Схема: {proxy_url.split('://')[0] if '://' in proxy_url else 'unknown'}")
						
						if proxy_url.startswith("socks5://"):
							logger.error(f"   httpx-socks установлен: {'✅ ДА' if SOCKS5_SUPPORT else '❌ НЕТ'}")
							if SOCKS5_SUPPORT and SOCKS5_VERSION:
								logger.error(f"   Версия httpx-socks: {SOCKS5_VERSION}")
						
						if "Connection refused by destination host" in error_str:
							logger.error(f"⚠️ КРИТИЧЕСКАЯ ПРОБЛЕМА: Прокси подключился, но не может подключиться к YooKassa API")
							logger.error(f"   → Это означает: подключение к прокси {proxy_host_port} успешно,")
							logger.error(f"     но прокси не может подключиться к api.yookassa.ru")
							logger.error(f"   ВОЗМОЖНЫЕ ПРИЧИНЫ:")
							logger.error(f"   1) Прокси блокирует подключение к api.yookassa.ru (черный список доменов)")
							logger.error(f"   2) Прокси не может разрешить DNS для api.yookassa.ru")
							logger.error(f"   3) Прокси не имеет доступа к YooKassa API (геоблокировка)")
							logger.error(f"   4) Прокси не поддерживает подключение к HTTPS сайтам")
							logger.error(f"   РЕШЕНИЯ:")
							logger.error(f"   → Попробуйте другой прокси, который разрешает доступ к YooKassa")
							logger.error(f"   → Или используйте прямое подключение (если YooKassa доступен без прокси)")
							logger.error(f"   → Проверьте настройки прокси - возможно нужен whitelist для api.yookassa.ru")
						
						if attempt < max_attempts:
							await asyncio.sleep(1.0)
							continue
						error_msg = f"Прокси не может подключиться к YooKassa API. Ошибка: {error_str}"
						raise RuntimeError(error_msg) from exc
				
				# Обычный ConnectError
				if isinstance(exc, httpx.ConnectError):
					last_error = exc
					proxy_info = f" (через прокси: {masked_proxy})" if proxy_url and masked_proxy else " (без прокси)"
					logger.error(
						f"🔌 ОШИБКА ПОДКЛЮЧЕНИЯ к YooKassa API{proxy_info} "
						f"(попытка {attempt}/{max_attempts})"
					)
					logger.error(f"🔌 Детали ошибки: {error_str}")
					
					if proxy_url:
						# Извлекаем информацию о прокси для диагностики
						proxy_host_port = "unknown"
						if "@" in proxy_url:
							proxy_host_port = proxy_url.split("@")[1]
						elif "://" in proxy_url:
							proxy_host_port = proxy_url.split("://")[1]
							if "@" in proxy_host_port:
								proxy_host_port = proxy_host_port.split("@")[1]
						
						logger.error(f"⚠️ ДИАГНОСТИКА ПРОКСИ:")
						logger.error(f"   Прокси: {masked_proxy}")
						logger.error(f"   Хост:порт: {proxy_host_port}")
						logger.error(f"   Схема: {proxy_url.split('://')[0] if '://' in proxy_url else 'unknown'}")
						
						if proxy_url.startswith("socks5://"):
							logger.error(f"   httpx-socks установлен: {'✅ ДА' if SOCKS5_SUPPORT else '❌ НЕТ'}")
							if SOCKS5_SUPPORT and SOCKS5_VERSION:
								logger.error(f"   Версия httpx-socks: {SOCKS5_VERSION}")
						
						logger.error(f"⚠️ ВОЗМОЖНЫЕ ПРИЧИНЫ:")
						logger.error(f"   1) Прокси недоступен или порт закрыт: {proxy_host_port}")
						logger.error(f"   2) Неправильные логин/пароль для прокси")
						logger.error(f"   3) Прокси не поддерживает SOCKS5 (если используется socks5://)")
						logger.error(f"   4) Прокси блокирует подключения с этого IP")
						logger.error(f"   5) httpx-socks не установлен (для SOCKS5): {'❌ НЕ УСТАНОВЛЕН' if not SOCKS5_SUPPORT and proxy_url.startswith('socks5://') else '✅ УСТАНОВЛЕН'}")
						
						# Проверяем специфичные ошибки
						if "Connection refused" in error_str or "refused" in error_str.lower():
							logger.error(f"   → Прокси явно отказывает в подключении (Connection refused)")
							logger.error(f"   → Проверьте доступность прокси: telnet {proxy_host_port.split(':')[0]} {proxy_host_port.split(':')[1] if ':' in proxy_host_port else '8000'}")
						elif "timeout" in error_str.lower():
							logger.error(f"   → Таймаут при подключении к прокси")
							logger.error(f"   → Прокси может быть перегружен или недоступен")
						elif "name resolution" in error_str.lower() or "not known" in error_str.lower():
							logger.error(f"   → Не удается разрешить имя прокси сервера")
							logger.error(f"   → Проверьте правильность адреса прокси")
					
					if attempt < max_attempts:
						await asyncio.sleep(1.0)
						continue
					error_msg = f"Не удалось подключиться к YooKassa API после {max_attempts} попыток."
					if proxy_url:
						error_msg += f" Прокси: {masked_proxy}. Ошибка: {error_str}. Проверьте доступность прокси и настройки."
					raise RuntimeError(error_msg) from exc
				
				# Для всех остальных исключений (кроме TimeoutException, ConnectError, ProxyError)
				last_error = exc
				logger.exception(f"Неожиданная ошибка при подключении к YooKassa API (попытка {attempt}/{max_attempts}): {exc}")
				# Для неожиданных ошибок нет смысла ретраить много раз — пробрасываем сразу.
				raise RuntimeError(f"Ошибка при подключении к YooKassa API: {exc}") from exc

		# Теоретически сюда не дойдём, но оставляем на всякий случай.
		raise RuntimeError(f"Не удалось создать платёж в YooKassa. Последняя ошибка: {last_error}")  # pragma: no cover


# Цена по планам (руб.), можно вынести в БД/админку
PLAN_PRICES_RUB: dict[str, int] = {
	"P1D_50K": 79,
	"P7D_125K": 110,
	"P7D_300K": 229,
	"P30D_1M": 749,
	"P30D_5M": 3199,
}


