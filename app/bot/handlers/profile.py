from aiogram import Router, F
from aiogram.types import CallbackQuery
from sqlalchemy import select, func
from datetime import datetime, timezone, timedelta
import asyncio

from app.bot.keyboards.profile import profile_menu_kb, payments_back_kb, referral_kb
from app.bot.keyboards.help import help_menu_kb
from app.bot.keyboards.main import main_menu_reply_kb
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.notifications import notify_admins_new_user
from app.db.session import async_session_maker
from app.db.models import User, Payment, Usage
from app.services.billing import ensure_balance, PLANS

router = Router()


async def _ensure_user(session, cb: CallbackQuery) -> tuple[User, bool]:
	"""
	Создаёт или получает пользователя из БД.
	
	Returns:
		Кортеж (user, is_new) - пользователь и флаг, был ли он только что создан
	"""
	from loguru import logger
	result = await session.execute(select(User).where(User.tg_id == cb.from_user.id))
	user = result.scalar_one_or_none()
	if user:
		logger.debug(f"Пользователь {cb.from_user.id} уже существует в БД (user_id={user.id})")
		updated_username = cb.from_user.username or None
		if user.username != updated_username:
			user.username = updated_username
		return user, False

	logger.info(f"Пользователь {cb.from_user.id} НЕ найден в БД, создаем нового")
	user = User(
		tg_id=cb.from_user.id,
		username=cb.from_user.username or None,
		ref_code=f"ref{cb.from_user.id}",
	)
	session.add(user)
	await session.flush()
	logger.info(f"Новый пользователь создан: tg_id={user.tg_id}, user_id={user.id}")
	return user, True


def _format_tokens(value: int) -> str:
	return f"{value:,}".replace(",", " ")


@router.callback_query(F.data == "menu_profile")
async def on_profile(cb: CallbackQuery) -> None:
	await cb.answer()
	
	async with async_session_maker() as session:
		user, is_new = await _ensure_user(session, cb)
		# Отправляем уведомление администраторам в фоне, если пользователь новый
		if is_new:
			from loguru import logger
			logger.info(f"Обнаружен новый пользователь в profile: tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(cb.bot, user, cb.from_user.full_name))
		
		balance = await ensure_balance(session, user.tg_id)
		
		# Подсчитываем статистику использования токенов
		usage_stats = await session.execute(
			select(Usage.model, func.sum(Usage.tokens_used).label("total"))
			.where(Usage.user_id == user.id)
			.group_by(Usage.model)
		)
		stats_dict = {row.model: row.total for row in usage_stats.all()}
		total_spent = sum(stats_dict.values())
		
		await session.commit()

	tokens = balance.tokens or 0
	
	# Проверяем подписку и вычисляем дни до окончания
	subscription_info = ""
	if balance.expires_at:
		now = datetime.now(timezone.utc)
		expires_at_utc = balance.expires_at.replace(tzinfo=timezone.utc) if balance.expires_at.tzinfo is None else balance.expires_at
		
		if expires_at_utc > now:
			delta = expires_at_utc - now
			days_left = delta.days
			if days_left >= 0:
				subscription_info = f"\nДо завершения подписки осталось: {days_left} дней"
	
	# Формируем статистику
	stats_lines = []
	if total_spent > 0:
		# ChatGPT (все режимы с gpt в названии модели)
		chatgpt_total = sum(v for k, v in stats_dict.items() if "gpt" in k.lower() or "chatgpt" in k.lower())
		if chatgpt_total > 0:
			stats_lines.append(f"- ChatGPT: {_format_tokens(chatgpt_total)}")
		
		# Другие модели (если есть)
		for model, amount in stats_dict.items():
			if "gpt" not in model.lower() and "chatgpt" not in model.lower():
				model_name = model.replace("_", " ").title()
				stats_lines.append(f"- {model_name}: {_format_tokens(amount)}")
	
	if not stats_lines:
		stats_lines.append("- ChatGPT: 0")
	
	stats_text = "\n".join(stats_lines)
	
	user_id = str(cb.from_user.id)
	text = (
		"👤 Мой профиль\n\n"
		f"ID: <code>{user_id}</code>\n"
		f"Имя: {cb.from_user.full_name}\n"
		f"Баланс: {_format_tokens(tokens)} токенов{subscription_info}\n\n"
		"На какие сервисы хватит баланса? · примерно:\n"
		"• 2 000 запросов к GPT‑5 (текст)\n"
		"• 400 запросов с анализом фото\n"
		"• 333 минуты расшифровки аудио\n"
		"• 100 000 символов перевода текста в голос\n\n"
		f"🔸 Потрачено: {_format_tokens(total_spent)} токенов\n"
		f"{stats_text}\n\n"
		"ℹ️ Расход зависит от длины запросов и выбранного режима."
	)
	await safe_edit_text(cb.message, text, reply_markup=profile_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data == "profile_payments")
async def profile_payments(cb: CallbackQuery) -> None:
	"""Отображает историю платежей пользователя."""
	# Отвечаем на callback_query сразу, чтобы избежать ошибки "query is too old"
	await cb.answer()
	
	async with async_session_maker() as session:
		user, is_new = await _ensure_user(session, cb)
		# Отправляем уведомление администраторам в фоне, если пользователь новый
		if is_new:
			from loguru import logger
			logger.info(f"Обнаружен новый пользователь в profile_payments: tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(cb.bot, user, cb.from_user.full_name))
		result = await session.execute(
			select(Payment).where(Payment.user_id == user.id).order_by(Payment.created_at.desc()).limit(20)
		)
		payments = result.scalars().all()

	if not payments:
		body = "История платежей пока пустая."
	else:
		lines = []
		# Эмодзи для статусов согласно референсу
		status_emoji = {"pending": "⏳", "succeeded": "🟢", "paid": "🟢", "canceled": "🔴", "failed": "🔴"}
		
		# Московское время для форматирования
		msk_timezone = timezone(timedelta(hours=3))
		
		for payment in payments:
			# Извлекаем номер счета из provider_id (формат: "invoice_number:yookassa_id")
			invoice_number = None
			if payment.provider_id:
				parts = payment.provider_id.split(":")
				if len(parts) > 0 and parts[0].isdigit():
					invoice_number = parts[0]
			
			# Если номер не найден в provider_id, используем ID платежа
			if not invoice_number:
				invoice_number = str(payment.id)
			
			# Форматируем дату по МСК
			created_at_utc = payment.created_at.replace(tzinfo=timezone.utc) if payment.created_at.tzinfo is None else payment.created_at
			created_at_msk = created_at_utc.astimezone(msk_timezone)
			created_at_str = created_at_msk.strftime("%Y-%m-%d %H:%M:%S")
			
			# Получаем количество токенов из плана
			tokens = PLANS.get(payment.plan_code, (0,))[0] if payment.plan_code in PLANS else 0
			
			# Форматируем строку платежа согласно референсу
			status_icon = status_emoji.get(payment.status, "⚪️")
			lines.append(
				f"{status_icon} №{invoice_number} {created_at_str}\n"
				f"Оплата {payment.amount_rub} руб. / {_format_tokens(tokens)} токенов"
			)
		body = "\n\n".join(lines)

	text = f"🧾 Мои платежи\n\nОтображены последние операции со счётом.\n\n{body}"
	await safe_edit_text(cb.message, text, reply_markup=payments_back_kb())


@router.callback_query(F.data == "profile_ref")
async def profile_ref(cb: CallbackQuery) -> None:
	await cb.answer()
	ref_link = f"https://t.me/{(await cb.bot.me()).username}?start=ref{cb.from_user.id}"
	text = (
		"👥 Реферальная программа\n\n"
		"Получайте 1 000 токенов за каждого приглашённого пользователя.\n\n"
		"🔗 Моя реферальная ссылка:\n"
		f"<code>{ref_link}</code>\n\n"
		"1. Поделитесь ссылкой ниже\n"
		"2. Друг запускает бота и авторизуется\n"
		"3. После активации ему начисляются токены, а вам — бонус 1 000 токенов\n\n"
		"💡 Начисление происходит автоматически сразу после регистрации приглашённого."
	)
	await safe_edit_text(cb.message, text, reply_markup=referral_kb(ref_link))


@router.callback_query(F.data == "profile_help")
async def profile_help(cb: CallbackQuery) -> None:
	await cb.answer()
	await safe_edit_text(cb.message, "❓ Выберите интересующий раздел", reply_markup=help_menu_kb())


@router.callback_query(F.data.startswith("profile_copy_id:"))
async def profile_copy_id(cb: CallbackQuery) -> None:
	"""Копирует ID пользователя - показывает в уведомлении для копирования."""
	user_id = cb.data.split(":", 1)[1]
	await cb.answer(text=user_id, show_alert=False)


@router.callback_query(F.data == "profile_back")
async def profile_back(cb: CallbackQuery) -> None:
	await on_profile(cb)
