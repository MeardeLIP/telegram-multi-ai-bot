from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from app.bot.keyboards.admin import admin_menu_kb, admin_cancel_kb, admin_stats_back_kb, admin_broadcast_confirm_kb
from app.bot.keyboards.main import main_menu_kb
from app.bot.utils.auth import is_admin
from app.bot.utils.tg import safe_edit_text
from app.db.session import async_session_maker
from app.db.models import User, Balance, Payment
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.services.billing import grant_tokens, get_user_balance, deduct_tokens, get_user_usage_stats, get_user_usage_history, PLANS
from app.services.payments import PLAN_PRICES_RUB


class AdminTopUpStates(StatesGroup):
	wait_tg_id = State()
	wait_amount = State()


class AdminCheckBalanceStates(StatesGroup):
	wait_tg_id = State()


class AdminDeductStates(StatesGroup):
	wait_tg_id = State()
	wait_amount = State()


class AdminUsageStatsStates(StatesGroup):
	wait_tg_id = State()


class AdminUsageHistoryStates(StatesGroup):
	wait_tg_id = State()


class AdminBroadcastStates(StatesGroup):
	wait_message = State()
	wait_confirm = State()


router = Router()


async def _ensure_admin(cb: CallbackQuery) -> bool:
	if not is_admin(cb.from_user.id):
		await cb.answer("Недостаточно прав", show_alert=True)
		return False
	return True


@router.callback_query(F.data == "menu_admin")
async def admin_menu(cb: CallbackQuery, state: FSMContext) -> None:
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.clear()
	await safe_edit_text(
		cb.message,
		"👑 Админ-панель\n\nВыберите действие:",
		reply_markup=admin_menu_kb(),
	)


@router.callback_query(F.data == "admin_topup")
async def admin_topup_start(cb: CallbackQuery, state: FSMContext) -> None:
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.set_state(AdminTopUpStates.wait_tg_id)
	await state.update_data(admin_message_id=cb.message.message_id)
	await safe_edit_text(
		cb.message,
		"Введите TG ID пользователя, которому нужно начислить токены:",
		reply_markup=admin_cancel_kb(),
	)


@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(cb: CallbackQuery, state: FSMContext) -> None:
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.clear()
	await safe_edit_text(
		cb.message,
		"👑 Админ-панель\n\nДействие отменено. Выберите следующую операцию:",
		reply_markup=admin_menu_kb(),
	)


@router.message(AdminTopUpStates.wait_tg_id)
async def admin_topup_get_tg(message: Message, state: FSMContext) -> None:
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		target_tg_id = int(text)
	except ValueError:
		await message.answer("Введите TG ID числом (пример: 123456789).")
		return
	await state.update_data(target_tg_id=target_tg_id)
	await message.answer(
		"Теперь отправьте количество токенов, которое хотите начислить (целое число > 0)."
	)
	await state.set_state(AdminTopUpStates.wait_amount)


@router.message(AdminTopUpStates.wait_amount)
async def admin_topup_amount(message: Message, state: FSMContext) -> None:
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		amount = int(text)
	except ValueError:
		await message.answer("Введите количество токенов числом (пример: 50000).")
		return
	if amount <= 0:
		await message.answer("Количество токенов должно быть больше нуля.")
		return

	data = await state.get_data()
	target_tg_id = data.get("target_tg_id")
	admin_message_id = data.get("admin_message_id")

	if not target_tg_id:
		await message.answer("TG ID пользователя не найден. Начните заново.", reply_markup=admin_menu_kb())
		await state.clear()
		return

	async with async_session_maker() as session:
		balance = await grant_tokens(session, tg_id=target_tg_id, amount=amount)
		await session.commit()

	logger.info(
		f"Админ {message.from_user.id} начислил {amount} токенов пользователю {target_tg_id}. Новый баланс: {balance.tokens}"
	)

	result_text = (
		f"✅ Пополнение выполнено\n\n"
		f"Пользователь: <code>{target_tg_id}</code>\n"
		f"Начислено: {amount} токенов\n"
		f"Текущий баланс: {balance.tokens or 0}\n\n"
		"Выберите следующую операцию:"
	)

	if admin_message_id:
		try:
			await message.bot.edit_message_text(
				result_text,
				chat_id=message.chat.id,
				message_id=admin_message_id,
				reply_markup=admin_menu_kb(),
				parse_mode="HTML",
			)
		except Exception:
			await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	else:
		await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())

	await state.clear()


@router.callback_query(F.data == "admin_check_balance")
async def admin_check_balance_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс проверки баланса пользователя."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.set_state(AdminCheckBalanceStates.wait_tg_id)
	await state.update_data(admin_message_id=cb.message.message_id)
	await safe_edit_text(
		cb.message,
		"Введите TG ID пользователя, баланс которого хотите проверить:",
		reply_markup=admin_cancel_kb(),
	)
	await cb.answer()


@router.message(AdminCheckBalanceStates.wait_tg_id)
async def admin_check_balance_get_tg_id(message: Message, state: FSMContext) -> None:
	"""Получает TG ID и выводит баланс пользователя."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		target_tg_id = int(text)
	except ValueError:
		await message.answer("Введите TG ID числом (пример: 123456789).")
		return
	
	data = await state.get_data()
	admin_message_id = data.get("admin_message_id")
	
	async with async_session_maker() as session:
		balance_info = await get_user_balance(session, target_tg_id)
	
	if not balance_info:
		result_text = f"❌ Пользователь с TG ID <code>{target_tg_id}</code> не найден.\n\nВыберите следующую операцию:"
	else:
		created_at_str = balance_info["created_at"].strftime("%d.%m.%Y %H:%M") if balance_info["created_at"] else "Не указано"
		username_str = balance_info["username"] or "Не указано"
		subscription_str = balance_info["subscription_tier"] or "Нет"
		expires_at_str = balance_info["expires_at"].strftime("%d.%m.%Y %H:%M") if balance_info["expires_at"] else "Не указано"
		
		result_text = (
			f"💰 Баланс пользователя\n\n"
			f"TG ID: <code>{balance_info['tg_id']}</code>\n"
			f"Внутренний ID: <code>{balance_info['user_id']}</code>\n"
			f"Username: @{username_str}\n"
			f"Текущий баланс: {balance_info['tokens']:,} токенов\n"
			f"Подписка: {subscription_str}\n"
			f"Истекает: {expires_at_str}\n"
			f"Дата регистрации: {created_at_str}\n\n"
			f"Выберите следующую операцию:"
		)
	
	if admin_message_id:
		try:
			await message.bot.edit_message_text(
				result_text,
				chat_id=message.chat.id,
				message_id=admin_message_id,
				reply_markup=admin_menu_kb(),
				parse_mode="HTML",
			)
		except Exception:
			await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	else:
		await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	
	await state.clear()


@router.callback_query(F.data == "admin_deduct")
async def admin_deduct_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс списания токенов у пользователя."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.set_state(AdminDeductStates.wait_tg_id)
	await state.update_data(admin_message_id=cb.message.message_id)
	await safe_edit_text(
		cb.message,
		"Введите TG ID пользователя, у которого нужно списать токены:",
		reply_markup=admin_cancel_kb(),
	)
	await cb.answer()


@router.message(AdminDeductStates.wait_tg_id)
async def admin_deduct_get_tg_id(message: Message, state: FSMContext) -> None:
	"""Получает TG ID и переходит к ожиданию количества токенов."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		target_tg_id = int(text)
	except ValueError:
		await message.answer("Введите TG ID числом (пример: 123456789).")
		return
	await state.update_data(target_tg_id=target_tg_id)
	await message.answer(
		"Теперь отправьте количество токенов, которое хотите списать (целое число > 0)."
	)
	await state.set_state(AdminDeductStates.wait_amount)


@router.message(AdminDeductStates.wait_amount)
async def admin_deduct_get_amount(message: Message, state: FSMContext) -> None:
	"""Получает количество токенов и списывает их."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		amount = int(text)
	except ValueError:
		await message.answer("Введите количество токенов числом (пример: 5000).")
		return
	if amount <= 0:
		await message.answer("Количество токенов должно быть больше нуля.")
		return
	
	data = await state.get_data()
	target_tg_id = data.get("target_tg_id")
	admin_message_id = data.get("admin_message_id")
	
	if not target_tg_id:
		await message.answer("TG ID пользователя не найден. Начните заново.", reply_markup=admin_menu_kb())
		await state.clear()
		return
	
	async with async_session_maker() as session:
		balance, success = await deduct_tokens(session, tg_id=target_tg_id, amount=amount)
		if success:
			await session.commit()
			logger.info(
				f"Админ {message.from_user.id} списал {amount} токенов у пользователя {target_tg_id}. Новый баланс: {balance.tokens}"
			)
			result_text = (
				f"✅ Списание выполнено\n\n"
				f"Пользователь: <code>{target_tg_id}</code>\n"
				f"Списано: {amount} токенов\n"
				f"Текущий баланс: {balance.tokens or 0:,}\n\n"
				f"Выберите следующую операцию:"
			)
		else:
			await session.rollback()
			result_text = (
				f"❌ Недостаточно токенов для списания\n\n"
				f"Пользователь: <code>{target_tg_id}</code>\n"
				f"Попытка списать: {amount} токенов\n"
				f"Текущий баланс: {balance.tokens or 0:,}\n\n"
				f"Выберите следующую операцию:"
			)
	
	if admin_message_id:
		try:
			await message.bot.edit_message_text(
				result_text,
				chat_id=message.chat.id,
				message_id=admin_message_id,
				reply_markup=admin_menu_kb(),
				parse_mode="HTML",
			)
		except Exception:
			await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	else:
		await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	
	await state.clear()


@router.callback_query(F.data == "admin_usage_stats")
async def admin_usage_stats_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс просмотра статистики запросов пользователя."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.set_state(AdminUsageStatsStates.wait_tg_id)
	await state.update_data(admin_message_id=cb.message.message_id)
	await safe_edit_text(
		cb.message,
		"Введите TG ID пользователя, статистику запросов которого хотите посмотреть:",
		reply_markup=admin_cancel_kb(),
	)
	await cb.answer()


@router.message(AdminUsageStatsStates.wait_tg_id)
async def admin_usage_stats_get_tg_id(message: Message, state: FSMContext) -> None:
	"""Получает TG ID и выводит статистику запросов пользователя."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		target_tg_id = int(text)
	except ValueError:
		await message.answer("Введите TG ID числом (пример: 123456789).")
		return
	
	data = await state.get_data()
	admin_message_id = data.get("admin_message_id")
	
	async with async_session_maker() as session:
		stats = await get_user_usage_stats(session, target_tg_id)
	
	if not stats:
		result_text = f"❌ Пользователь с TG ID <code>{target_tg_id}</code> не найден.\n\nВыберите следующую операцию:"
	else:
		result_text = (
			f"📊 Статистика запросов\n\n"
			f"Пользователь: <code>{stats['tg_id']}</code>\n"
			f"Внутренний ID: <code>{stats['user_id']}</code>\n\n"
			f"Общее количество запросов: {stats['total_requests']}\n"
			f"Успешных: {stats['successful_requests']}\n"
			f"Неуспешных: {stats['failed_requests']}\n"
			f"Всего потрачено токенов: {stats['total_tokens']:,}\n\n"
			f"Выберите следующую операцию:"
		)
	
	if admin_message_id:
		try:
			await message.bot.edit_message_text(
				result_text,
				chat_id=message.chat.id,
				message_id=admin_message_id,
				reply_markup=admin_menu_kb(),
				parse_mode="HTML",
			)
		except Exception:
			await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	else:
		await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	
	await state.clear()


@router.callback_query(F.data == "admin_usage_history")
async def admin_usage_history_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс просмотра истории запросов пользователя."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	await state.set_state(AdminUsageHistoryStates.wait_tg_id)
	await state.update_data(admin_message_id=cb.message.message_id)
	await safe_edit_text(
		cb.message,
		"Введите TG ID пользователя, историю запросов которого хотите посмотреть:",
		reply_markup=admin_cancel_kb(),
	)
	await cb.answer()


@router.message(AdminUsageHistoryStates.wait_tg_id)
async def admin_usage_history_get_tg_id(message: Message, state: FSMContext) -> None:
	"""Получает TG ID и выводит историю запросов пользователя."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	text = (message.text or "").strip()
	try:
		target_tg_id = int(text)
	except ValueError:
		await message.answer("Введите TG ID числом (пример: 123456789).")
		return
	
	data = await state.get_data()
	admin_message_id = data.get("admin_message_id")
	
	async with async_session_maker() as session:
		history = await get_user_usage_history(session, target_tg_id, limit=50)
	
	if history is None:
		result_text = f"❌ Пользователь с TG ID <code>{target_tg_id}</code> не найден.\n\nВыберите следующую операцию:"
	elif not history:
		result_text = f"📜 История запросов\n\nПользователь: <code>{target_tg_id}</code>\n\nЗапросов не найдено.\n\nВыберите следующую операцию:"
	else:
		history_lines = []
		for usage in history[:20]:  # Показываем только последние 20 запросов
			date_str = usage.created_at.strftime("%d.%m.%Y %H:%M")
			status = "✅" if usage.success else "❌"
			error_info = f"\nОшибка: {usage.error_message}" if usage.error_message else ""
			history_lines.append(
				f"{status} {date_str} | {usage.mode} | {usage.model} | {usage.tokens_used} токенов{error_info}"
			)
		
		result_text = (
			f"📜 История запросов (последние {len(history_lines)} из {len(history)})\n\n"
			f"Пользователь: <code>{target_tg_id}</code>\n\n"
		)
		result_text += "\n".join(history_lines)
		result_text += "\n\nВыберите следующую операцию:"
	
	if admin_message_id:
		try:
			await message.bot.edit_message_text(
				result_text,
				chat_id=message.chat.id,
				message_id=admin_message_id,
				reply_markup=admin_menu_kb(),
				parse_mode="HTML",
			)
		except Exception:
			# Если сообщение слишком длинное, отправляем отдельным сообщением
			await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	else:
		await message.answer(result_text, parse_mode="HTML", reply_markup=admin_menu_kb())
	
	await state.clear()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(cb: CallbackQuery) -> None:
	"""Отображает статистику всех пользователей с их балансами."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	async with async_session_maker() as session:
		# Получаем всех пользователей
		users_result = await session.execute(
			select(User).order_by(User.created_at.desc())
		)
		users = users_result.scalars().all()
		
		# Для каждого пользователя получаем баланс отдельным запросом
		users_with_balance = []
		for user in users:
			balance_result = await session.execute(
				select(Balance).where(Balance.user_id == user.id)
			)
			balance = balance_result.scalar_one_or_none()
			# Сохраняем баланс в объект пользователя для удобства
			if balance:
				user.balance = balance
			users_with_balance.append((user, balance))
	
	if not users_with_balance:
		text = "📊 Статистика\n\nПользователей не найдено."
		await safe_edit_text(cb.message, text, reply_markup=admin_stats_back_kb(), parse_mode="HTML")
		return
	
	# Формируем список пользователей
	stats_lines = []
	for user, balance in users_with_balance:
		# Получаем баланс пользователя
		tokens = 0
		if balance:
			tokens = balance.tokens or 0
		
		# Формируем никнейм (без ссылки, чтобы не показывалось превью Telegram)
		username = user.username or "Не указан"
		
		# Формируем строку с ID в теге <code> для легкого копирования
		# Формат: "Id: <code>738973626</code> Ник : ivang Токенов: 100000"
		stats_lines.append(f"Id: <code>{user.tg_id}</code> Ник : {username} Токенов: {tokens}")
	
	# Объединяем все строки
	stats_text = "\n".join(stats_lines)
	
	# Формируем итоговое сообщение
	text = f"📊 Статистика\n\nВсего пользователей: {len(users_with_balance)}\n\n{stats_text}"
	
	# Telegram имеет лимит на длину сообщения (4096 символов), разбиваем если нужно
	if len(text) > 4000:
		# Разбиваем на части
		parts = []
		current_part = f"📊 Статистика\n\nВсего пользователей: {len(users_with_balance)}\n\n"
		
		for line in stats_lines:
			if len(current_part + line + "\n") > 4000:
				parts.append(current_part)
				current_part = line + "\n"
			else:
				current_part += line + "\n"
		
		if current_part:
			parts.append(current_part)
		
		# Отправляем первую часть
		await safe_edit_text(cb.message, parts[0], reply_markup=admin_stats_back_kb(), parse_mode="HTML")
		
		# Отправляем остальные части отдельными сообщениями
		for part in parts[1:]:
			await cb.message.answer(part, reply_markup=admin_stats_back_kb(), parse_mode="HTML")
	else:
		await safe_edit_text(cb.message, text, reply_markup=admin_stats_back_kb(), parse_mode="HTML")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс отправки уведомления всем пользователям."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	await state.set_state(AdminBroadcastStates.wait_message)
	await safe_edit_text(
		cb.message,
		"📢 Отправка уведомления всем пользователям\n\n"
		"Введите текст сообщения, которое будет отправлено всем пользователям бота:",
		reply_markup=admin_cancel_kb(),
	)
	await cb.answer()


@router.message(AdminBroadcastStates.wait_message)
async def admin_broadcast_message(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод текста уведомления и показывает превью."""
	if not is_admin(message.from_user.id):
		await state.clear()
		await message.answer("❌ Недостаточно прав.", reply_markup=main_menu_kb())
		return
	
	text = message.text or message.caption or ""
	if not text.strip():
		await message.answer(
			"❌ Сообщение не может быть пустым. Введите текст уведомления:",
			reply_markup=admin_cancel_kb(),
		)
		return
	
	# Получаем количество пользователей для информации
	async with async_session_maker() as session:
		result = await session.execute(select(User))
		users = result.scalars().all()
		user_count = len(users)
	
	await state.update_data(message_text=text, user_count=user_count)
	await state.set_state(AdminBroadcastStates.wait_confirm)
	
	preview_text = (
		"📢 Превью уведомления\n\n"
		f"{text}\n\n"
		f"━━━━━━━━━━━━━━━━━━━━\n"
		f"📊 Будет отправлено пользователям: {user_count}\n\n"
		"Подтвердите отправку:"
	)
	
	await message.answer(preview_text, reply_markup=admin_broadcast_confirm_kb())


@router.callback_query(F.data == "admin_broadcast_confirm")
async def admin_broadcast_confirm(cb: CallbackQuery, state: FSMContext) -> None:
	"""Отправляет уведомление всем пользователям."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	data = await state.get_data()
	message_text = data.get("message_text", "")
	user_count = data.get("user_count", 0)
	
	if not message_text:
		await cb.answer("Ошибка: текст сообщения не найден", show_alert=True)
		await state.clear()
		return
	
	await cb.answer("Начинаю отправку...")
	
	# Обновляем сообщение с информацией о начале отправки
	await safe_edit_text(
		cb.message,
		f"📢 Отправка уведомления\n\n"
		"⏳ Идет отправка сообщения всем пользователям...\n"
		"Пожалуйста, подождите.",
		reply_markup=None,
	)
	
	# Получаем всех пользователей
	async with async_session_maker() as session:
		result = await session.execute(select(User))
		users = result.scalars().all()
	
	# Отправляем сообщения асинхронно
	import asyncio
	from aiogram.exceptions import TelegramBadRequest
	
	success_count = 0
	failed_count = 0
	
	async def send_to_user(user: User):
		nonlocal success_count, failed_count
		try:
			await cb.bot.send_message(
				chat_id=user.tg_id,
				text=message_text,
				parse_mode="HTML",
			)
			success_count += 1
		except TelegramBadRequest as e:
			# Пользователь заблокировал бота или другой ошибка
			logger.warning(f"Не удалось отправить сообщение пользователю {user.tg_id}: {e}")
			failed_count += 1
		except Exception as e:
			logger.error(f"Ошибка при отправке сообщения пользователю {user.tg_id}: {e}")
			failed_count += 1
		# Небольшая задержка, чтобы не перегружать API
		await asyncio.sleep(0.05)
	
	# Отправляем сообщения с ограничением параллелизма
	semaphore = asyncio.Semaphore(10)  # Максимум 10 одновременных отправок
	
	async def send_with_semaphore(user: User):
		async with semaphore:
			await send_to_user(user)
	
	# Создаем задачи для всех пользователей
	tasks = [send_with_semaphore(user) for user in users]
	await asyncio.gather(*tasks)
	
	# Обновляем сообщение с результатами
	result_text = (
		f"✅ Отправка завершена!\n\n"
		f"📊 Статистика:\n"
		f"• Успешно отправлено: {success_count}\n"
		f"• Ошибок: {failed_count}\n"
		f"• Всего пользователей: {user_count}"
	)
	
	await safe_edit_text(
		cb.message,
		result_text,
		reply_markup=admin_stats_back_kb(),
	)
	
	await state.clear()
	logger.info(f"Админ {cb.from_user.id} отправил уведомление {user_count} пользователям. Успешно: {success_count}, Ошибок: {failed_count}")


@router.callback_query(F.data == "admin_subscriptions")
async def admin_subscriptions(cb: CallbackQuery) -> None:
	"""Отображает все покупки подписок с информацией о пользователях, сумме, дате, токенах и периоде."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	async with async_session_maker() as session:
		# Получаем все успешные платежи с информацией о пользователях
		# Сортируем по дате создания (новые сначала), ограничиваем последними 100
		result = await session.execute(
			select(Payment, User)
			.join(User, Payment.user_id == User.id)
			.where(Payment.status == "succeeded")
			.order_by(Payment.created_at.desc())
			.limit(100)
		)
		payments_with_users = result.all()
	
	if not payments_with_users:
		text = "💳 Покупки подписок\n\nУспешных покупок не найдено."
		await safe_edit_text(cb.message, text, reply_markup=admin_stats_back_kb(), parse_mode="HTML")
		return
	
	# Формируем список покупок
	subscription_lines = []
	for payment, user in payments_with_users:
		# Получаем информацию о тарифе
		plan_code = payment.plan_code
		plan_info = PLANS.get(plan_code)
		if plan_info:
			tokens, period = plan_info
			days = period.days
		else:
			# Если план не найден, используем значения по умолчанию
			tokens = 0
			days = 0
		
		amount = payment.amount_rub
		
		# Форматируем дату
		date_str = payment.created_at.strftime("%d.%m.%Y %H:%M")
		
		# Форматируем username
		username = user.username or "Не указан"
		
		# Форматируем количество токенов
		tokens_str = f"{tokens:,}".replace(",", " ") if tokens > 0 else "0"
		
		# Формируем строку с информацией о покупке
		subscription_lines.append(
			f"📅 {date_str} | "
			f"ID: <code>{user.tg_id}</code> | "
			f"@{username} | "
			f"{amount} руб. | "
			f"{tokens_str} токенов | "
			f"{days} дней | "
			f"{plan_code}"
		)
	
	# Формируем итоговое сообщение
	header = f"💳 Покупки подписок\n\nВсего покупок: {len(subscription_lines)}\n\n"
	stats_text = "\n".join(subscription_lines)
	text = header + stats_text
	
	# Telegram имеет лимит на длину сообщения (4096 символов), разбиваем если нужно
	if len(text) > 4000:
		# Разбиваем на части
		parts = []
		current_part = header
		
		for line in subscription_lines:
			if len(current_part + line + "\n") > 4000:
				parts.append(current_part)
				current_part = line + "\n"
			else:
				current_part += line + "\n"
		
		if current_part:
			parts.append(current_part)
		
		# Отправляем первую часть
		await safe_edit_text(cb.message, parts[0], reply_markup=admin_stats_back_kb(), parse_mode="HTML")
		
		# Отправляем остальные части отдельными сообщениями
		for part in parts[1:]:
			await cb.message.answer(part, reply_markup=admin_stats_back_kb(), parse_mode="HTML")
	else:
		await safe_edit_text(cb.message, text, reply_markup=admin_stats_back_kb(), parse_mode="HTML")
