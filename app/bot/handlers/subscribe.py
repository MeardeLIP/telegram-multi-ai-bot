import httpx
import asyncio
import time
from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, LinkPreviewOptions
from loguru import logger

from app.bot.keyboards.subscribe import subscribe_menu_kb, payment_method_kb, payment_invoice_kb
from app.bot.keyboards.main import main_menu_kb, main_menu_reply_kb
from app.config import get_settings
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.auth import is_admin
from app.services.billing import PLANS, calculate_requests_for_plan
from app.services.payments import PLAN_PRICES_RUB
from app.db.session import async_session_maker
from app.db.models import Payment, User
from sqlalchemy import select

router = Router()


@router.callback_query(F.data == "menu_subscribe")
async def open_subscribe(cb: CallbackQuery) -> None:
	await cb.answer()
	await safe_edit_text(cb.message, "💎 Оформить подписку. Выберите тариф:", reply_markup=subscribe_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data.startswith("plan:"))
async def choose_plan(cb: CallbackQuery) -> None:
	"""Показывает экран выбора способа оплаты с информацией о количестве запросов."""
	await cb.answer()
	plan_code = cb.data.split(":", 1)[1]
	
	if plan_code not in PLANS:
		await cb.answer("Неизвестный тариф", show_alert=True)
		return
	
	tokens, period = PLANS[plan_code]
	price = PLAN_PRICES_RUB.get(plan_code, 0)
	
	# Форматируем количество токенов и дней
	tokens_str = f"{tokens:,}".replace(",", " ")
	days = period.days
	
	# Рассчитываем количество запросов
	requests = calculate_requests_for_plan(tokens)
	
	# Формируем текст согласно референсу
	# Форматируем числа с пробелами для тысяч
	def format_num(n: int) -> str:
		return f"{n:,}".replace(",", " ")
	
	text = (
		f"🏦 Выберите способ оплаты\n\n"
		f"ℹ️ Вы выбрали тариф {days} дней — {tokens_str} токенов — {price} руб. На сколько запросов хватит?\n\n"
		f"💬 ChatGPT и языковые модели · примерно\n\n"
		f"- {format_num(requests['chatgpt_text'])} запросов к ChatGPT 5 Mini;\n\n"
		f"- {format_num(requests['chatgpt_vision'])} запросов к ChatGPT 5 Mini с обработкой фотографий;\n\n"
		f"- Включение истории, создание диалогов с разными моделями и своими промптами.\n\n"
		f"🌆 Создание изображений:\n\n"
		f"- GPT Image: {format_num(requests['gpt_image'])} запросов;\n\n"
		f"- Замена лиц: {format_num(requests['faceswap'])} запросов для замены лиц.\n\n"
		f"✂️ Работа с фото:\n\n"
		f"- Улучшение фото: {format_num(requests['photo_enhance'])} запросов;\n\n"
		f"- Замена фона: {format_num(requests['photo_replace_bg'])} запросов;\n\n"
		f"- Удаление фона: {format_num(requests['photo_remove_bg'])} запросов.\n\n"
		f"🎙 Работа с аудио:\n\n"
		f"- {format_num(requests['stt_minutes'])} минут расшифровки аудио;\n\n"
		f"- {format_num(requests['tts_chars'])} символов перевода текста в голос.\n\n"
		f"* Токены — это общая валюта для всех нейросетей в нашем боте и расчеты сделаны конкретно для каждой нейросети. В случае использования всех количество запросов будет меняться. Чем больше пакет токенов, тем лучше."
	)
	
	await safe_edit_text(cb.message, text, reply_markup=payment_method_kb(plan_code))


@router.callback_query(F.data.startswith("payment_method:card:"))
async def choose_payment_method(cb: CallbackQuery) -> None:
	"""Создает счет после выбора способа оплаты."""
	await cb.answer()
	plan_code = cb.data.split(":", 2)[2]
	settings = get_settings()
	
	if plan_code not in PLANS:
		await safe_edit_text(cb.message, "❌ Неизвестный тариф", reply_markup=payment_method_kb(plan_code))
		return
	
	tokens, period = PLANS[plan_code]
	price = PLAN_PRICES_RUB.get(plan_code, 0)
	
	# Форматируем количество токенов и дней
	tokens_str = f"{tokens:,}".replace(",", " ")
	days = period.days
	
	# Проверка токена больше не нужна для YooKassa ссылок
	
	# Показываем, что идет создание счета
	# Если сообщение содержит фото - удаляем его и отправляем новое текстовое сообщение
	message_was_deleted = False
	status_message = None
	
	if cb.message.photo:
		try:
			await cb.message.delete()
			message_was_deleted = True
		except Exception:
			pass
		status_message = await cb.bot.send_message(
			cb.message.chat.id,
			"⏳ Создание счёта...",
			reply_markup=None
		)
	else:
		await safe_edit_text(
			cb.message,
			"⏳ Создание счёта...",
			reply_markup=None
		)
		status_message = cb.message
	
	# Создаем счет через API
	payment_data = None
	# ВАЖНО: для обращения бота к API используем внутренний URL,
	# чтобы не зависеть от внешнего IP и возможных блокировок/NAT.
	api_base = getattr(settings, "api_internal_url", settings.public_base_url)
	if api_base.endswith("/"):
		api_base = api_base[:-1]
	api_url = f"{api_base}/payments/create"
	logger.info(f"Создание платежа через API: {api_url}")
	
	# Retry механизм с экспоненциальной задержкой
	max_attempts = 3
	base_delay = 1.0  # Начальная задержка в секундах
	last_error = None
	# Уменьшаем таймаут для запросов бота к API (API сам ждет YooKassa)
	# Если API возвращает 502, значит YooKassa уже не ответил, повторять долго нет смысла
	request_timeout = 30.0  # 30 секунд на запрос к API
	# Общий таймаут для всей операции (максимум 2 минуты)
	total_timeout = 120.0
	operation_start = time.time()
	
	for attempt in range(1, max_attempts + 1):
		# Проверяем общий таймаут операции
		elapsed = time.time() - operation_start
		if elapsed >= total_timeout:
			logger.error(f"Превышен общий таймаут операции ({total_timeout}s)")
			error_message = (
				"❌ Превышено время ожидания при создании счета.\n\n"
				"Попробуйте позже или обратитесь в поддержку."
			)
			if message_was_deleted:
				await status_message.edit_text(
					error_message,
					reply_markup=payment_method_kb(plan_code)
				)
			else:
				await safe_edit_text(
					status_message,
					error_message,
					reply_markup=payment_method_kb(plan_code)
				)
			return
		
		try:
			# Таймаут уменьшен: API сам ждет YooKassa, если он не ответил - повтор быстро
			async with httpx.AsyncClient(timeout=request_timeout) as cli:
				resp = await cli.post(
					api_url,
					json={"plan_code": plan_code, "user_id": cb.from_user.id},
				)
				resp.raise_for_status()
				payment_data = resp.json()
				logger.info(f"Платеж успешно создан: payment_id={payment_data.get('payment_id')}")
				break  # Успешно, выходим из цикла
		except httpx.HTTPStatusError as exc:
			last_error = exc
			status_code = exc.response.status_code
			error_detail = exc.response.text[:200] if exc.response.text else "Нет деталей"
			
			logger.warning(
				f"Попытка {attempt}/{max_attempts}: HTTP {status_code} при создании счёта: {api_url}, "
				f"детали: {error_detail}"
			)
			
			# Для 502 и 503 ошибок делаем повтор, для остальных - сразу возвращаем ошибку
			if status_code in (502, 503) and attempt < max_attempts:
				delay = base_delay * (2 ** (attempt - 1))  # Экспоненциальная задержка: 1s, 2s, 4s
				logger.info(f"Повтор через {delay} секунд...")
				await asyncio.sleep(delay)
				continue
			else:
				# Для других HTTP ошибок или последней попытки - возвращаем ошибку
				logger.error(
					f"Не удалось создать счёт: HTTP {status_code}, детали: {error_detail}"
				)
				error_message = (
					f"❌ Ошибка сервера при создании счета (HTTP {status_code}).\n\n"
					f"Попробуйте позже или обратитесь в поддержку."
				)
				if message_was_deleted:
					await status_message.edit_text(
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				else:
					await safe_edit_text(
						status_message,
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				return
		except httpx.TimeoutException as exc:
			last_error = exc
			logger.warning(f"Попытка {attempt}/{max_attempts}: Таймаут при создании счёта: {api_url}")
			if attempt < max_attempts:
				delay = base_delay * (2 ** (attempt - 1))
				logger.info(f"Повтор через {delay} секунд...")
				await asyncio.sleep(delay)
				continue
			else:
				logger.error(f"Таймаут при создании счёта после {max_attempts} попыток: {api_url}, ошибка: {exc}")
				error_message = (
					"❌ Таймаут при создании счета.\n\n"
					"Сервер не отвечает. Попробуйте позже или обратитесь в поддержку."
				)
				if message_was_deleted:
					await status_message.edit_text(
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				else:
					await safe_edit_text(
						status_message,
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				return
		except httpx.ConnectError as exc:
			last_error = exc
			logger.warning(f"Попытка {attempt}/{max_attempts}: Не удалось подключиться к API: {api_url}")
			if attempt < max_attempts:
				delay = base_delay * (2 ** (attempt - 1))
				logger.info(f"Повтор через {delay} секунд...")
				await asyncio.sleep(delay)
				continue
			else:
				logger.error(f"Не удалось подключиться к API после {max_attempts} попыток: {api_url}, ошибка: {exc}")
				error_message = (
					"❌ API сервер недоступен.\n\n"
					"Проверьте настройки API_INTERNAL_URL в конфигурации или попробуйте позже."
				)
				if message_was_deleted:
					await status_message.edit_text(
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				else:
					await safe_edit_text(
						status_message,
						error_message,
						reply_markup=payment_method_kb(plan_code)
					)
				return
		except Exception as exc:
			last_error = exc
			logger.exception(f"Попытка {attempt}/{max_attempts}: Неожиданная ошибка при создании счёта: {exc}")
			# Для неожиданных ошибок не делаем повтор - сразу возвращаем ошибку
			error_message = (
				"❌ Ошибка при создании счета.\n\n"
				"Попробуйте позже или обратитесь в поддержку."
			)
			if message_was_deleted:
				await status_message.edit_text(
					error_message,
					reply_markup=payment_method_kb(plan_code)
				)
			else:
				await safe_edit_text(
					status_message,
					error_message,
					reply_markup=payment_method_kb(plan_code)
				)
			return
	
	# Если после всех попыток payment_data все еще None
	if not payment_data:
		logger.error(f"Не удалось создать счёт после {max_attempts} попыток. Последняя ошибка: {last_error}")
		error_message = (
			"❌ Не удалось создать счет после нескольких попыток.\n\n"
			"Попробуйте позже или обратитесь в поддержку."
		)
		if message_was_deleted:
			await status_message.edit_text(
				error_message,
				reply_markup=payment_method_kb(plan_code)
			)
		else:
			await safe_edit_text(
				status_message,
				error_message,
				reply_markup=payment_method_kb(plan_code)
			)
		return
	
	if not payment_data:
		if message_was_deleted:
			await status_message.edit_text(
				"❌ Не удалось создать счет.\n\nПопробуйте позже или обратитесь в поддержку.",
				reply_markup=payment_method_kb(plan_code)
			)
		else:
			await safe_edit_text(
				status_message,
				"❌ Не удалось создать счет.\n\nПопробуйте позже или обратитесь в поддержку.",
				reply_markup=payment_method_kb(plan_code)
			)
		return
	
	# Форматируем дату создания в реальном времени по московскому времени (MSK, UTC+3)
	msk_timezone = timezone(timedelta(hours=3))  # Московское время UTC+3
	created_at_msk = datetime.now(msk_timezone)
	created_at = created_at_msk.strftime("%d.%m.%Y %H:%M")
	
	# Получаем ссылку на оплату
	payment_url = payment_data.get("payment_url")
	if not payment_url:
		if message_was_deleted:
			await status_message.edit_text(
				"❌ Не удалось получить ссылку на оплату.\n\nПопробуйте позже или обратитесь в поддержку.",
				reply_markup=payment_method_kb(plan_code)
			)
		else:
			await safe_edit_text(
				status_message,
				"❌ Не удалось получить ссылку на оплату.\n\nПопробуйте позже или обратитесь в поддержку.",
				reply_markup=payment_method_kb(plan_code)
			)
		return
	
	# Формируем текст согласно референсу с HTML форматированием
	# Номер счета в формате code для копирования
	# Убрали ссылку из текста, чтобы не показывалось превью картинки
	invoice_id = payment_data.get("invoice_id")
	text = (
		f"🧾 Счёт <code>№{invoice_id}</code> создан\n\n"
		f"🔹 Название товара: {days} дней — {tokens_str} токенов — {price} руб.\n\n"
		f"🏦 Способ оплаты: 💳 Карта, СБП и др. (ЮKassa)\n\n"
		f"💰 Стоимость: {price}.0 руб.\n\n"
		f"📅 Создан: {created_at}\n\n"
		f"⏰ Произведите оплату в течение 60 минут. После оплаты токены будут начислены автоматически.\n\n"
		f"Нажав «💸 Оплатить» вы соглашаетесь с условиями использования ЮKassa.\n\n"
		f"Нажмите кнопку «Оплатить» для перехода на страницу оплаты."
	)
	
	# Редактируем status_message (которое уже не содержит фото)
	if message_was_deleted:
		# Если сообщение было удалено, status_message - это новое текстовое сообщение
		await status_message.edit_text(
			text,
			reply_markup=payment_invoice_kb(payment_url),
			parse_mode="HTML",
			link_preview_options=LinkPreviewOptions(is_disabled=True)  # Отключаем превью ссылок (картинку от YooKassa)
		)
	else:
		# Если сообщение не было удалено, используем safe_edit_text
		await safe_edit_text(
			status_message,
			text,
			reply_markup=payment_invoice_kb(payment_url),
			parse_mode="HTML",
			disable_link_preview=True,  # Отключаем превью ссылок (картинку от YooKassa)
		)


# Обработчики Telegram Payments удалены - теперь используется оплата по ссылке через YooKassa
# Платежи обрабатываются через webhook /webhooks/yookassa в API


