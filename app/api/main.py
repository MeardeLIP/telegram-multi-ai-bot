from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import random
import sys
import asyncio
import logging
import os

# Исправление для Windows: используем WindowsSelectorEventLoopPolicy вместо ProactorEventLoop
# Это необходимо для работы psycopg (async PostgreSQL драйвер) на Windows
if sys.platform == "win32":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.db.session import async_session_maker
from app.db.models import Payment, User, PromoCode, Balance
from app.services.billing import apply_plan_payment, PLANS
from app.services.payments import YooKassaGateway, PLAN_PRICES_RUB, test_yookassa_connection

from app.config import get_settings

app = FastAPI(title="GPT-5 Bot API")
settings = get_settings()
logger = logging.getLogger(__name__)


@app.get("/health")
async def health() -> dict:
	return {"status": "ok"}


@app.get("/api/diagnostic/yookassa")
async def diagnostic_yookassa() -> dict:
	"""
	Диагностический endpoint для проверки доступности YooKassa API.
	Проверяет DNS, TCP соединение, SSL handshake и HTTPS запрос.
	"""
	try:
		results = await test_yookassa_connection()
		return {
			"status": "completed",
			"results": results,
			"summary": {
				"all_checks_passed": all(
					check["status"] == "success"
					for check in results.values()
					if isinstance(check, dict) and "status" in check
				)
			}
		}
	except Exception as e:
		return {
			"status": "error",
			"error": str(e),
			"error_type": type(e).__name__
		}


@app.post("/webhooks/yookassa")
async def yookassa_webhook(request: Request) -> JSONResponse:
	"""
	Обработчик webhook от YooKassa для уведомлений об изменении статуса платежа.
	"""
	try:
		payload = await request.json()
		logger.info(f"📥 Получен webhook от YooKassa: {payload.get('event', 'unknown')}")
		
		if not payload:
			logger.warning("⚠️ Пустой payload в webhook")
			raise HTTPException(status_code=400, detail="empty")

		# Получаем объект платежа (может быть в payload.object или в корне payload)
		payment_object = payload.get("object", payload)
		
		payment_id = payment_object.get("id") or payload.get("id")
		status = payment_object.get("status") or payload.get("status")
		
		logger.info(f"🔍 Обработка платежа: payment_id={payment_id}, status={status}")
		
		# Metadata может быть в object.metadata или в корне payload
		metadata = payment_object.get("metadata") or payload.get("metadata", {})
		plan_code = metadata.get("plan_code") if isinstance(metadata, dict) else None
		user_tg_id = metadata.get("user_id") if isinstance(metadata, dict) else None
		
		logger.info(f"🔍 Metadata: plan_code={plan_code}, user_tg_id={user_tg_id}")

		async with async_session_maker() as session:  # type: AsyncSession
			# Проверяем все необходимые данные перед обработкой
			if payment_id and status == "succeeded" and user_tg_id is not None and plan_code is not None and plan_code in PLAN_PRICES_RUB:
				logger.info(f"✅ Платеж успешен, начинаем обработку: payment_id={payment_id}, user_tg_id={user_tg_id}, plan_code={plan_code}")
				
				# Находим платеж по provider_id (содержит YooKassa payment_id)
				payment_result = await session.execute(
					select(Payment).where(Payment.provider_id.like(f"%:{payment_id}"))
				)
				payment = payment_result.scalar_one_or_none()
				
				if payment:
					logger.info(f"📋 Найден платеж в БД: payment.id={payment.id}, status={payment.status}")
					
					# Обновляем статус платежа
					if payment.status != "succeeded":
						payment.status = "succeeded"
						await session.flush()
						logger.info(f"✅ Статус платежа обновлен на 'succeeded'")
					else:
						logger.info(f"ℹ️ Платеж уже был обработан ранее (status=succeeded)")
				else:
					logger.warning(f"⚠️ Платеж с provider_id содержащим '{payment_id}' не найден в БД")
				
				# Начисляем токены и применяем подписку
				await _mark_paid_and_apply(session, int(user_tg_id), str(plan_code), payment_id)
				
				logger.info(f"✅ Платеж успешно обработан: токены начислены, подписка применена")
			else:
				logger.warning(f"⚠️ Платеж не обработан: payment_id={payment_id}, status={status}, user_tg_id={user_tg_id}, plan_code={plan_code}")
				if status != "succeeded":
					logger.info(f"ℹ️ Статус платежа '{status}' - ожидаем 'succeeded'")
				if not user_tg_id:
					logger.warning(f"⚠️ user_id отсутствует в metadata")
				if not plan_code:
					logger.warning(f"⚠️ plan_code отсутствует в metadata")
				if plan_code and plan_code not in PLAN_PRICES_RUB:
					logger.warning(f"⚠️ Неизвестный plan_code: {plan_code}")

		return JSONResponse({"ok": True})
	except Exception as e:
		logger.exception(f"❌ Ошибка при обработке webhook от YooKassa: {e}")
		# Все равно возвращаем 200, чтобы YooKassa не повторял запрос
		return JSONResponse({"ok": False, "error": str(e)}, status_code=200)


async def _mark_paid_and_apply(session: AsyncSession, user_tg_id: int, plan_code: str, payment_id: str | None = None) -> None:
	"""
	Отмечает платеж как успешный и начисляет токены пользователю.
	
	Args:
		session: Сессия базы данных
		user_tg_id: Telegram ID пользователя (не внутренний ID!)
		plan_code: Код тарифа
		payment_id: ID платежа от YooKassa (опционально, для логирования)
	"""
	logger.info(f"💰 Начисление токенов: user_tg_id={user_tg_id}, plan_code={plan_code}, payment_id={payment_id}")
	
	# Находим пользователя по Telegram ID
	user_result = await session.execute(select(User).where(User.tg_id == user_tg_id))
	user = user_result.scalar_one_or_none()
	
	if not user:
		logger.error(f"❌ Пользователь с tg_id={user_tg_id} не найден в БД")
		raise ValueError(f"User with tg_id {user_tg_id} not found")
	
	logger.info(f"✅ Пользователь найден: id={user.id}, tg_id={user.tg_id}")
	
	# Начисление по плану (передаем tg_id)
	balance = await apply_plan_payment(session, user.tg_id, plan_code)  # type: ignore[arg-type]
	
	tokens, period = PLANS[plan_code]
	logger.info(f"✅ Токены начислены: user_tg_id={user_tg_id}, tokens={balance.tokens}, plan_code={plan_code}")
	
	await session.commit()
	logger.info(f"✅ Изменения зафиксированы в БД")
	
	# Отправляем уведомление пользователю в бот (асинхронно, не блокируем ответ)
	try:
		from aiogram import Bot
		from app.config import get_settings
		settings = get_settings()
		bot = Bot(token=settings.bot_token)
		
		tokens_str = f"{tokens:,}".replace(",", " ")
		days = period.days
		message_text = (
			f"✅ Платеж успешно обработан!\n\n"
			f"💰 Начислено: {tokens_str} токенов\n"
			f"📅 Срок действия: {days} дней\n\n"
			f"Спасибо за покупку! Теперь вы можете пользоваться всеми возможностями бота."
		)
		
		await bot.send_message(chat_id=user_tg_id, text=message_text)
		logger.info(f"✅ Уведомление отправлено пользователю tg_id={user_tg_id}")
		await bot.session.close()
	except Exception as e:
		logger.error(f"⚠️ Не удалось отправить уведомление пользователю tg_id={user_tg_id}: {e}")
		# Не прерываем выполнение, если не удалось отправить уведомление


class TelegramPaymentConfirm(BaseModel):
	payment_id: int
	telegram_payment_id: str | None = None


@app.post("/payments/create")
async def create_payment(payload: dict) -> dict:
	"""
	Создает платеж через YooKassa API.
	
	Args:
		payload: Словарь с ключами:
			- plan_code: код тарифа (например, "P1D_50K")
			- user_id: Telegram ID пользователя
			
	Returns:
		Словарь с данными созданного платежа
		
	Raises:
		HTTPException: При ошибках валидации или создания платежа
	"""
	plan_code = payload.get("plan_code")
	user_id = int(payload.get("user_id"))
	customer_email = payload.get("customer_email")  # Опционально
	customer_phone = payload.get("customer_phone")  # Опционально
	
	logger.info(f"Создание платежа: plan_code={plan_code}, user_id={user_id}")
	
	# Если нет email и телефона, пытаемся получить email из базы данных
	if not customer_email and not customer_phone:
		async with async_session_maker() as session:
			user_result = await session.execute(select(User).where(User.tg_id == user_id))
			user = user_result.scalar_one_or_none()
			# TODO: Добавить поле email в модель User, если нужно хранить email пользователей
			# Пока используем fallback в create_invoice

	if plan_code not in PLAN_PRICES_RUB:
		logger.warning(f"Неизвестный тариф: {plan_code}")
		raise HTTPException(status_code=400, detail=f"unknown plan: {plan_code}")

	amount = PLAN_PRICES_RUB[plan_code]
	logger.info(f"Сумма платежа: {amount} руб. для тарифа {plan_code}")
	
	# Проверяем настройки прокси перед созданием платежа
	proxy_url = os.getenv("YOOKASSA_PROXY", "").strip()
	if not proxy_url:
		proxy_url = getattr(settings, "yookassa_proxy", "").strip()
	
	if proxy_url:
		# Маскируем пароль в логах
		masked_proxy = proxy_url
		if "@" in proxy_url:
			parts = proxy_url.split("@")
			if len(parts) == 2:
				auth_part = parts[0]
				if ":" in auth_part:
					user_pass = auth_part.split(":", 1)
					if len(user_pass) == 2:
						masked_proxy = f"{user_pass[0]}:****@{parts[1]}"
		logger.info(f"🔍 Прокси настроен для YooKassa: {masked_proxy}")
		
		# Проверяем поддержку SOCKS5
		if proxy_url.startswith("socks5://"):
			try:
				from httpx_socks import AsyncProxyTransport
				logger.info("✅ httpx-socks доступен для SOCKS5 прокси")
			except ImportError:
				logger.error("❌ httpx-socks НЕ УСТАНОВЛЕН! SOCKS5 прокси не будет работать!")
				logger.error("   Установите: pip install httpx-socks")
	else:
		logger.warning("⚠️ Прокси для YooKassa не настроен, используется прямое подключение")
	
	gw = YooKassaGateway()
	try:
		logger.info(f"Отправка запроса в YooKassa для создания платежа: amount={amount}, plan_code={plan_code}")
		invoice = await gw.create_invoice(
			amount,
			f"Подписка {plan_code}",
			f"{settings.public_base_url}/thankyou",
			metadata={"user_id": user_id, "plan_code": plan_code},
			customer_email=customer_email,
			customer_phone=customer_phone,
		)
		logger.info(f"Платеж успешно создан в YooKassa: payment_id={invoice.get('id')}")
	except RuntimeError as exc:
		error_msg = str(exc)
		logger.error(
			f"Ошибка при создании платежа в YooKassa: {error_msg}, "
			f"plan_code={plan_code}, user_id={user_id}, amount={amount}"
		)
		
		# Проверяем, является ли это ошибкой "Receipt is missing"
		if "Receipt is missing" in error_msg or "receipt" in error_msg.lower():
			detail_msg = (
				"YooKassa требует отправку чека (receipt), но он не настроен. "
				"Отключите требование чека в настройках магазина YooKassa: "
				"Настройки → Прием платежей → Отключить отправку чеков в ФНС. "
				"Или обратитесь в поддержку YooKassa для настройки чека."
			)
			# Возвращаем 400 (Bad Request), так как это проблема конфигурации, а не сервера
			raise HTTPException(status_code=400, detail=detail_msg) from exc
		
		# Возвращаем более информативное сообщение об ошибке
		detail_msg = (
			f"Не удалось создать платеж в YooKassa: {error_msg}. "
			"Возможные причины: недоступность YooKassa API, проблемы с прокси или сетью."
		)
		raise HTTPException(status_code=502, detail=detail_msg) from exc
	except Exception as exc:
		error_type = type(exc).__name__
		error_msg = str(exc)
		logger.exception(
			f"Неожиданная ошибка при создании платежа: {error_type}: {error_msg}, "
			f"plan_code={plan_code}, user_id={user_id}, amount={amount}"
		)
		raise HTTPException(
			status_code=500,
			detail=f"Внутренняя ошибка сервера при создании платежа: {error_type}: {error_msg}"
		) from exc
	
	# Сохраняем информацию о платеже в БД
	async with async_session_maker() as session:  # type: AsyncSession
		# Находим или создаем пользователя
		user_result = await session.execute(select(User).where(User.tg_id == user_id))
		user = user_result.scalar_one_or_none()
		
		if not user:
			# Создаем пользователя, если его нет
			user = User(tg_id=user_id, username=None, ref_code=f"ref{user_id}")
			session.add(user)
			await session.flush()
		
		# Генерируем уникальный 5-значный номер счета
		# Генерируем номер до тех пор, пока не найдем уникальный
		max_attempts = 10
		invoice_number = None
		for _ in range(max_attempts):
			candidate = random.randint(10000, 99999)
			# Проверяем, что такой номер не используется в provider_id
			# (можно также сохранить в отдельном поле, но для простоты используем provider_id)
			existing_payment_result = await session.execute(
				select(Payment).where(Payment.provider_id == str(candidate))
			)
			if not existing_payment_result.scalar_one_or_none():
				invoice_number = candidate
				break
		
		# Если не удалось найти уникальный номер за 10 попыток, используем последний сгенерированный
		if invoice_number is None:
			invoice_number = random.randint(10000, 99999)
		
		# Сохраняем номер счета в provider_id вместе с ID от YooKassa
		# Формат: "invoice_number:yookassa_id"
		provider_id_with_invoice = f"{invoice_number}:{invoice['id']}"
		
		# Создаем запись о платеже
		payment = Payment(
			user_id=user.id,
			plan_code=plan_code,
			amount_rub=amount,
			status="pending",
			provider="yookassa",
			provider_id=provider_id_with_invoice
		)
		session.add(payment)
		await session.flush()
		await session.commit()
		
		# Сохраняем ID до выхода из блока session
		payment_id = payment.id
		user_db_id = user.id
		invoice_id = invoice_number
	
	tokens, period = PLANS[plan_code]
	tokens_str = f"{tokens:,}".replace(",", " ")
	days = period.days
	title = f"{days} дн · {tokens_str} токенов"
	description = f"{days} дней — {tokens_str} токенов — {amount} руб."

	# Получаем ссылку на оплату из ответа YooKassa
	confirmation_url = invoice.get("confirmation", {}).get("confirmation_url") if invoice else None
	
	return {
		"payment_id": payment_id,
		"user_db_id": user_db_id,
		"invoice_id": invoice_id,
		"title": title[:32],
		"description": description[:255],
		"currency": "RUB",
		"amount": amount,
		"price_label": description,
		"plan_code": plan_code,
		"tokens": tokens,
		"payment_url": confirmation_url,  # Ссылка на страницу оплаты YooKassa
		"days": days,
		"yookassa_payment_id": invoice["id"],
	}


def _is_admin(user_id: int) -> bool:
	try:
		ids = [int(x) for x in settings.admin_ids.split(",") if x.strip()]
		return user_id in ids
	except Exception:
		return False


@app.post("/admin/promocode/create")
async def admin_create_promocode(payload: dict) -> dict:
	admin_id = int(payload.get("admin_id", 0))
	if not _is_admin(admin_id):
		raise HTTPException(status_code=403, detail="forbidden")

	code = payload.get("code", "").upper().strip()
	if not code or not code.isalnum():
		raise HTTPException(status_code=400, detail="invalid code")
	
	bonus = int(payload.get("tokens_bonus", 0))
	discount_percent = int(payload.get("discount_percent", 0))
	max_uses = int(payload.get("max_uses", 1))
	expires_at = payload.get("expires_at")  # ISO format string или None
	
	# Парсим дату окончания, если указана
	expires_at_dt = None
	if expires_at:
		from datetime import datetime
		try:
			expires_at_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
		except ValueError:
			raise HTTPException(status_code=400, detail="invalid expires_at format")

	async with async_session_maker() as session:
		# Проверяем, существует ли уже такой промокод
		existing = await session.get(PromoCode, code)
		if existing:
			raise HTTPException(status_code=400, detail="promocode already exists")
		
		pc = PromoCode(
			code=code,
			tokens_bonus=bonus,
			discount_percent=discount_percent,
			max_uses=max_uses if max_uses > 0 else 999999,
			expires_at=expires_at_dt
		)
		session.add(pc)
		await session.commit()

	return {"ok": True, "code": code}


@app.post("/admin/users/tokens")
async def admin_set_tokens(payload: dict) -> dict:
	admin_id = int(payload.get("admin_id", 0))
	if not _is_admin(admin_id):
		raise HTTPException(status_code=403, detail="forbidden")
	user_id = int(payload["user_id"])
	tokens = int(payload["tokens"])

	async with async_session_maker() as session:
		bal = await session.get(Balance, user_id)
		if not bal:
			bal = Balance(user_id=user_id, tokens=tokens)
			session.add(bal)
		else:
			bal.tokens = tokens
		await session.commit()
	return {"ok": True}


@app.post("/payments/telegram/confirm")
async def confirm_telegram_payment(request: Request, data: TelegramPaymentConfirm) -> dict:
	token = request.headers.get("x-webhook-token")
	if token != settings.webhook_secret:
		raise HTTPException(status_code=403, detail="forbidden")

	async with async_session_maker() as session:
		payment = await session.get(Payment, data.payment_id)
		if not payment:
			raise HTTPException(status_code=404, detail="payment_not_found")
		if payment.status == "succeeded":
			return {"ok": True, "status": "already_confirmed"}
		
		payment.status = "succeeded"
		if data.telegram_payment_id:
			suffix = f"|tg:{data.telegram_payment_id}"
			payment.provider_id = f"{payment.provider_id or ''}{suffix}"

		await _mark_paid_and_apply(session, payment.user_id, payment.plan_code)

	return {"ok": True}


@app.get("/thankyou")
async def thankyou_page(request: Request) -> HTMLResponse:
	"""
	Страница благодарности после успешной оплаты через YooKassa.
	Показывает сообщение об успешной оплате и кнопку для возврата в бот.
	"""
	bot_username = settings.bot_username or ""
	
	# Формируем ссылку на бота
	if bot_username:
		bot_link = f"https://t.me/{bot_username}"
		bot_link_tg = f"tg://resolve?domain={bot_username}"
	else:
		# Если username не указан, используем универсальную ссылку
		bot_link = "#"
		bot_link_tg = "#"
	
	html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
	<meta charset="UTF-8">
	<meta name="viewport" content="width=device-width, initial-scale=1.0">
	<title>Спасибо за оплату!</title>
	<style>
		* {{
			margin: 0;
			padding: 0;
			box-sizing: border-box;
		}}
		
		body {{
			font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
			background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
			min-height: 100vh;
			display: flex;
			align-items: center;
			justify-content: center;
			padding: 20px;
		}}
		
		.container {{
			background: white;
			border-radius: 20px;
			padding: 40px;
			max-width: 500px;
			width: 100%;
			box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
			text-align: center;
		}}
		
		.checkmark {{
			width: 80px;
			height: 80px;
			border-radius: 50%;
			background: #4CAF50;
			margin: 0 auto 30px;
			display: flex;
			align-items: center;
			justify-content: center;
			animation: scaleIn 0.5s ease-out;
		}}
		
		.checkmark::after {{
			content: '✓';
			color: white;
			font-size: 50px;
			font-weight: bold;
		}}
		
		@keyframes scaleIn {{
			from {{
				transform: scale(0);
			}}
			to {{
				transform: scale(1);
			}}
		}}
		
		h1 {{
			color: #333;
			margin-bottom: 20px;
			font-size: 28px;
		}}
		
		p {{
			color: #666;
			line-height: 1.6;
			margin-bottom: 30px;
			font-size: 16px;
		}}
		
		.bot-button {{
			display: inline-block;
			background: #0088cc;
			color: white;
			text-decoration: none;
			padding: 15px 30px;
			border-radius: 10px;
			font-size: 18px;
			font-weight: 600;
			transition: all 0.3s ease;
			margin-top: 10px;
		}}
		
		.bot-button:hover {{
			background: #006ba3;
			transform: translateY(-2px);
			box-shadow: 0 5px 15px rgba(0, 136, 204, 0.4);
		}}
		
		.bot-button:active {{
			transform: translateY(0);
		}}
		
		.info-box {{
			background: #f0f7ff;
			border-left: 4px solid #0088cc;
			padding: 15px;
			margin: 20px 0;
			border-radius: 5px;
			text-align: left;
		}}
		
		.info-box p {{
			margin: 0;
			font-size: 14px;
			color: #555;
		}}
		
		.auto-redirect {{
			margin-top: 20px;
			font-size: 14px;
			color: #999;
		}}
	</style>
</head>
<body>
	<div class="container">
		<div class="checkmark"></div>
		<h1>Спасибо за оплату!</h1>
		<p>Ваш платёж успешно обработан.</p>
		
		<div class="info-box">
			<p>💰 Токены будут начислены автоматически в течение нескольких минут.</p>
			<p>📱 Вернитесь в бот, чтобы продолжить работу.</p>
		</div>
		
		<a href="{bot_link_tg}" class="bot-button" id="botButton">
			Вернуться в бот
		</a>
		
		<div class="auto-redirect" id="redirectInfo">
			Автоматический переход через <span id="countdown">5</span> сек...
		</div>
	</div>
	
	<script>
		let countdown = 5;
		const countdownElement = document.getElementById('countdown');
		const redirectInfo = document.getElementById('redirectInfo');
		const botButton = document.getElementById('botButton');
		
		function updateCountdown() {{
			countdownElement.textContent = countdown;
			if (countdown <= 0) {{
				redirectInfo.style.display = 'none';
				if (botButton.href !== '#') {{
					window.location.href = botButton.href;
				}}
			}} else {{
				countdown--;
				setTimeout(updateCountdown, 1000);
			}}
		}}
		
		// Запускаем обратный отсчет только если есть ссылка на бота
		if (botButton.href !== '#') {{
			setTimeout(updateCountdown, 1000);
		}} else {{
			redirectInfo.style.display = 'none';
		}}
	</script>
</body>
</html>
	"""
	
	return HTMLResponse(content=html_content)


