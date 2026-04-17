from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta
from loguru import logger

from app.bot.keyboards.promo_admin import (
	admin_promo_menu_kb, admin_promo_back_kb, admin_promo_cancel_kb,
	admin_promo_list_kb, admin_promo_edit_kb
)
from app.bot.keyboards.admin import admin_menu_kb
from app.bot.utils.auth import is_admin
from app.bot.utils.tg import safe_edit_text
from app.db.session import async_session_maker
from app.db.models import PromoCode


class AdminPromoCreateStates(StatesGroup):
	wait_code = State()
	wait_tokens_bonus = State()
	wait_discount_percent = State()
	wait_max_uses = State()
	wait_valid_days = State()


class AdminPromoEditStates(StatesGroup):
	wait_code = State()
	wait_tokens_bonus = State()
	wait_discount_percent = State()
	wait_max_uses = State()
	wait_expires_at = State()


router = Router()


async def _ensure_admin(cb: CallbackQuery) -> bool:
	"""Проверяет, является ли пользователь администратором."""
	if not is_admin(cb.from_user.id):
		await cb.answer("Недостаточно прав", show_alert=True)
		return False
	return True


def _format_datetime(dt: datetime | None) -> str:
	"""Форматирует дату и время для отображения по МСК."""
	if not dt:
		return "Не ограничено"
	msk_timezone = timezone(timedelta(hours=3))
	# Если дата без timezone, считаем её UTC
	if dt.tzinfo is None:
		dt_utc = dt.replace(tzinfo=timezone.utc)
	else:
		dt_utc = dt
	dt_msk = dt_utc.astimezone(msk_timezone)
	return dt_msk.strftime("%d.%m.%Y %H:%M")


@router.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(cb: CallbackQuery) -> None:
	"""Главное меню управления промокодами."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	text = (
		"🎟 Управление промокодами\n\n"
		"Выберите действие:\n"
		"• Создать промокод\n"
		"• Просмотреть список промокодов\n"
		"• Редактировать или удалить промокод"
	)
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_menu_kb())


@router.callback_query(F.data == "admin_promo_create")
async def admin_promo_create_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс создания промокода."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	await state.set_state(AdminPromoCreateStates.wait_code)
	text = (
		"➕ Создание промокода\n\n"
		"Введите код промокода (только буквы и цифры, будет преобразован в верхний регистр):"
	)
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_cancel_kb())
	await cb.answer()


@router.message(AdminPromoCreateStates.wait_code)
async def admin_promo_create_code(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод кода промокода."""
	code = (message.text or "").strip().upper()
	
	if not code or not code.isalnum():
		await message.answer(
			"❌ Код промокода должен содержать только буквы и цифры. Введите код:",
			reply_markup=admin_promo_cancel_kb()
		)
		return
	
	# Проверяем, существует ли уже такой промокод
	async with async_session_maker() as session:
		existing = await session.get(PromoCode, code)
		if existing:
			await message.answer(
				f"❌ Промокод {code} уже существует. Введите другой код:",
				reply_markup=admin_promo_cancel_kb()
			)
			return
	
	await state.update_data(code=code)
	await state.set_state(AdminPromoCreateStates.wait_tokens_bonus)
	await message.answer(
		f"✅ Код промокода: {code}\n\n"
		"Введите количество токенов для начисления (бонус):"
	)


@router.message(AdminPromoCreateStates.wait_tokens_bonus)
async def admin_promo_create_tokens(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод бонусных токенов."""
	try:
		tokens_bonus = int(message.text or "0")
		if tokens_bonus < 0:
			raise ValueError
	except ValueError:
		await message.answer(
			"❌ Введите положительное число токенов:",
			reply_markup=admin_promo_cancel_kb()
		)
		return
	
	await state.update_data(tokens_bonus=tokens_bonus)
	await state.set_state(AdminPromoCreateStates.wait_discount_percent)
	await message.answer(
		f"✅ Бонус токенов: {tokens_bonus:,}\n\n"
		"Введите процент скидки (0-100, 0 если скидки нет):"
	)


@router.message(AdminPromoCreateStates.wait_discount_percent)
async def admin_promo_create_discount(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод процента скидки."""
	try:
		discount_percent = int(message.text or "0")
		if discount_percent < 0 or discount_percent > 100:
			raise ValueError
	except ValueError:
		await message.answer(
			"❌ Введите число от 0 до 100:",
			reply_markup=admin_promo_cancel_kb()
		)
		return
	
	await state.update_data(discount_percent=discount_percent)
	await state.set_state(AdminPromoCreateStates.wait_max_uses)
	await message.answer(
		f"✅ Процент скидки: {discount_percent}%\n\n"
		"Введите максимальное количество использований (0 = без ограничений):"
	)


@router.message(AdminPromoCreateStates.wait_max_uses)
async def admin_promo_create_max_uses(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод максимального количества использований."""
	try:
		max_uses = int(message.text or "1")
		if max_uses < 0:
			raise ValueError
	except ValueError:
		await message.answer(
			"❌ Введите положительное число или 0 (без ограничений):",
			reply_markup=admin_promo_cancel_kb()
		)
		return
	
	await state.update_data(max_uses=max_uses)
	await state.set_state(AdminPromoCreateStates.wait_valid_days)
	await message.answer(
		f"✅ Максимум использований: {max_uses if max_uses > 0 else 'Без ограничений'}\n\n"
		"Введите количество дней действия промокода (или 'нет' для бессрочного действия):"
	)


@router.message(AdminPromoCreateStates.wait_valid_days)
async def admin_promo_create_valid_days(message: Message, state: FSMContext) -> None:
	"""Обрабатывает ввод количества дней действия промокода."""
	valid_days_text = (message.text or "").strip().lower()
	valid_days = None
	expires_at = None
	
	if valid_days_text not in ["нет", "no", "n", ""]:
		try:
			valid_days = int(valid_days_text)
			if valid_days < 1:
				raise ValueError
			# Вычисляем expires_at на основе created_at + valid_days
			created_at = datetime.now(timezone.utc)
			expires_at = created_at + timedelta(days=valid_days)
		except ValueError:
			await message.answer(
				"❌ Введите положительное число дней или 'нет':",
				reply_markup=admin_promo_cancel_kb()
			)
			return
	
	data = await state.get_data()
	
	# Создаем промокод
	async with async_session_maker() as session:
		promo = PromoCode(
			code=data["code"],
			tokens_bonus=data["tokens_bonus"],
			discount_percent=data["discount_percent"],
			max_uses=data["max_uses"] if data["max_uses"] > 0 else 999999,  # Большое число вместо 0
			used_count=0,
			active=True,
			expires_at=expires_at,  # None если бессрочный, или вычисленная дата если указаны дни
			valid_days=valid_days  # None если бессрочный, или количество дней
		)
		session.add(promo)
		await session.commit()
	
	expires_str = _format_datetime(expires_at) if expires_at else "Не ограничено"
	valid_days_str = f"{valid_days} дней" if valid_days else "Бессрочный"
	
	await message.answer(
		f"✅ Промокод создан успешно!\n\n"
		f"Код: {data['code']}\n"
		f"Бонус токенов: {data['tokens_bonus']:,}\n"
		f"Процент скидки: {data['discount_percent']}%\n"
		f"Максимум использований: {data['max_uses'] if data['max_uses'] > 0 else 'Без ограничений'}\n"
		f"Действителен до: {expires_str}\n"
		f"Дней действия: {valid_days_str}",
		reply_markup=admin_promo_back_kb()
	)
	await state.clear()


@router.callback_query(F.data == "admin_promo_list")
async def admin_promo_list(cb: CallbackQuery) -> None:
	"""Показывает список всех промокодов."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	async with async_session_maker() as session:
		result = await session.execute(
			select(PromoCode).order_by(PromoCode.created_at.desc())
		)
		promocodes = result.scalars().all()
	
	if not promocodes:
		text = "📋 Список промокодов\n\nПромокоды не найдены."
		await safe_edit_text(cb.message, text, reply_markup=admin_promo_back_kb())
	else:
		text = f"📋 Список промокодов\n\nНайдено промокодов: {len(promocodes)}"
		await safe_edit_text(cb.message, text, reply_markup=admin_promo_list_kb(promocodes, page=0))
	
	await cb.answer()


@router.callback_query(F.data.startswith("admin_promo_list_page:"))
async def admin_promo_list_page(cb: CallbackQuery) -> None:
	"""Обрабатывает пагинацию списка промокодов."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	page = int(cb.data.split(":")[1])
	
	async with async_session_maker() as session:
		result = await session.execute(
			select(PromoCode).order_by(PromoCode.created_at.desc())
		)
		promocodes = result.scalars().all()
	
	text = f"📋 Список промокодов\n\nНайдено промокодов: {len(promocodes)}"
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_list_kb(promocodes, page=page))
	await cb.answer()


@router.callback_query(F.data.startswith("admin_promo_edit:"))
async def admin_promo_edit(cb: CallbackQuery) -> None:
	"""Показывает информацию о промокоде для редактирования."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await cb.answer("Промокод не найден", show_alert=True)
			return
		
		# Форматируем информацию о промокоде
		status = "✅ Активен" if promo.active else "❌ Неактивен"
		if promo.expires_at:
			# Проверяем, истек ли промокод
			expires_at_utc = promo.expires_at.replace(tzinfo=timezone.utc) if promo.expires_at.tzinfo is None else promo.expires_at
			if expires_at_utc < datetime.now(timezone.utc):
				status = "⏰ Истек"
		if promo.used_count >= promo.max_uses:
			status = "🔒 Исчерпан"
		
		expires_str = _format_datetime(promo.expires_at) if promo.expires_at else "Не ограничено"
		max_uses_str = f"{promo.max_uses:,}" if promo.max_uses < 999999 else "Без ограничений"
		
		text = (
			f"🎟 Редактирование промокода\n\n"
			f"Код: {promo.code}\n"
			f"Статус: {status}\n"
			f"Бонус токенов: {promo.tokens_bonus:,}\n"
			f"Процент скидки: {promo.discount_percent}%\n"
			f"Использовано: {promo.used_count:,} / {max_uses_str}\n"
			f"Действителен до: {expires_str}\n"
			f"Создан: {_format_datetime(promo.created_at)}"
		)
		
		await safe_edit_text(cb.message, text, reply_markup=admin_promo_edit_kb(promo_code))
		await cb.answer()


@router.callback_query(F.data.startswith("admin_promo_toggle:"))
async def admin_promo_toggle(cb: CallbackQuery) -> None:
	"""Включает/выключает промокод."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await cb.answer("Промокод не найден", show_alert=True)
			return
		
		# Сохраняем новое состояние
		new_active = not promo.active
		promo.active = new_active
		await session.commit()
		await session.refresh(promo)
		
		status = "включен" if new_active else "выключен"
		await cb.answer(f"Промокод {status}", show_alert=True)
		
		# Форматируем информацию о промокоде
		status_display = "✅ Активен" if promo.active else "❌ Неактивен"
		if promo.expires_at:
			expires_at_utc = promo.expires_at.replace(tzinfo=timezone.utc) if promo.expires_at.tzinfo is None else promo.expires_at
			if expires_at_utc < datetime.now(timezone.utc):
				status_display = "⏰ Истек"
		if promo.used_count >= promo.max_uses:
			status_display = "🔒 Исчерпан"
		
		expires_str = _format_datetime(promo.expires_at) if promo.expires_at else "Не ограничено"
		max_uses_str = f"{promo.max_uses:,}" if promo.max_uses < 999999 else "Без ограничений"
		
		text = (
			f"🎟 Редактирование промокода\n\n"
			f"Код: {promo.code}\n"
			f"Статус: {status_display}\n"
			f"Бонус токенов: {promo.tokens_bonus:,}\n"
			f"Процент скидки: {promo.discount_percent}%\n"
			f"Использовано: {promo.used_count:,} / {max_uses_str}\n"
			f"Действителен до: {expires_str}\n"
			f"Создан: {_format_datetime(promo.created_at)}"
		)
		
		await safe_edit_text(cb.message, text, reply_markup=admin_promo_edit_kb(promo_code))


@router.callback_query(F.data.startswith("admin_promo_delete:"))
async def admin_promo_delete(cb: CallbackQuery) -> None:
	"""Удаляет промокод."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await cb.answer("Промокод не найден", show_alert=True)
			return
		
		await session.delete(promo)
		await session.commit()
	
	await cb.answer("Промокод удален", show_alert=True)
	
	# Возвращаемся к списку промокодов
	await admin_promo_list(cb)


@router.callback_query(F.data.startswith("admin_promo_edit_tokens:"))
async def admin_promo_edit_tokens_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает редактирование бонусных токенов."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	await state.update_data(promo_code=promo_code)
	await state.set_state(AdminPromoEditStates.wait_tokens_bonus)
	
	text = f"💰 Изменение бонусных токенов\n\nВведите новое количество токенов для промокода {promo_code}:"
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_cancel_kb())
	await cb.answer()


@router.message(AdminPromoEditStates.wait_tokens_bonus)
async def admin_promo_edit_tokens(message: Message, state: FSMContext) -> None:
	"""Обрабатывает изменение бонусных токенов."""
	try:
		tokens_bonus = int(message.text or "0")
		if tokens_bonus < 0:
			raise ValueError
	except ValueError:
		await message.answer("❌ Введите положительное число токенов:", reply_markup=admin_promo_cancel_kb())
		return
	
	data = await state.get_data()
	promo_code = data["promo_code"]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await message.answer("❌ Промокод не найден", reply_markup=admin_promo_back_kb())
			await state.clear()
			return
		
		promo.tokens_bonus = tokens_bonus
		await session.commit()
		await session.refresh(promo)
	
	await message.answer(
		f"✅ Бонусные токены обновлены: {tokens_bonus:,}",
		reply_markup=admin_promo_back_kb()
	)
	await state.clear()


@router.callback_query(F.data.startswith("admin_promo_edit_discount:"))
async def admin_promo_edit_discount_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает редактирование процента скидки."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	await state.update_data(promo_code=promo_code)
	await state.set_state(AdminPromoEditStates.wait_discount_percent)
	
	text = f"📊 Изменение процента скидки\n\nВведите новый процент скидки (0-100) для промокода {promo_code}:"
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_cancel_kb())
	await cb.answer()


@router.message(AdminPromoEditStates.wait_discount_percent)
async def admin_promo_edit_discount(message: Message, state: FSMContext) -> None:
	"""Обрабатывает изменение процента скидки."""
	try:
		discount_percent = int(message.text or "0")
		if discount_percent < 0 or discount_percent > 100:
			raise ValueError
	except ValueError:
		await message.answer("❌ Введите число от 0 до 100:", reply_markup=admin_promo_cancel_kb())
		return
	
	data = await state.get_data()
	promo_code = data["promo_code"]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await message.answer("❌ Промокод не найден", reply_markup=admin_promo_back_kb())
			await state.clear()
			return
		
		promo.discount_percent = discount_percent
		await session.commit()
	
	await message.answer(
		f"✅ Процент скидки обновлен: {discount_percent}%",
		reply_markup=admin_promo_back_kb()
	)
	await state.clear()


@router.callback_query(F.data.startswith("admin_promo_edit_max_uses:"))
async def admin_promo_edit_max_uses_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает редактирование максимального количества использований."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	await state.update_data(promo_code=promo_code)
	await state.set_state(AdminPromoEditStates.wait_max_uses)
	
	text = f"🔢 Изменение максимального количества использований\n\nВведите новое значение (0 = без ограничений) для промокода {promo_code}:"
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_cancel_kb())
	await cb.answer()


@router.message(AdminPromoEditStates.wait_max_uses)
async def admin_promo_edit_max_uses(message: Message, state: FSMContext) -> None:
	"""Обрабатывает изменение максимального количества использований."""
	try:
		max_uses = int(message.text or "1")
		if max_uses < 0:
			raise ValueError
	except ValueError:
		await message.answer("❌ Введите положительное число или 0:", reply_markup=admin_promo_cancel_kb())
		return
	
	data = await state.get_data()
	promo_code = data["promo_code"]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await message.answer("❌ Промокод не найден", reply_markup=admin_promo_back_kb())
			await state.clear()
			return
		
		promo.max_uses = max_uses if max_uses > 0 else 999999
		await session.commit()
	
	max_uses_str = f"{max_uses:,}" if max_uses > 0 else "Без ограничений"
	await message.answer(
		f"✅ Максимум использований обновлен: {max_uses_str}",
		reply_markup=admin_promo_back_kb()
	)
	await state.clear()


@router.callback_query(F.data.startswith("admin_promo_edit_expires:"))
async def admin_promo_edit_expires_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает редактирование даты окончания действия."""
	await cb.answer()
	if not await _ensure_admin(cb):
		return
	
	promo_code = cb.data.split(":")[1]
	await state.update_data(promo_code=promo_code)
	await state.set_state(AdminPromoEditStates.wait_expires_at)
	
	text = (
		f"📅 Изменение даты окончания действия\n\n"
		f"Введите новую дату окончания (формат: ДД.ММ.ГГГГ ЧЧ:ММ) для промокода {promo_code}:\n"
		f"Или введите 'нет' для бессрочного действия:"
	)
	await safe_edit_text(cb.message, text, reply_markup=admin_promo_cancel_kb())
	await cb.answer()


@router.message(AdminPromoEditStates.wait_expires_at)
async def admin_promo_edit_expires(message: Message, state: FSMContext) -> None:
	"""Обрабатывает изменение даты окончания действия."""
	expires_text = (message.text or "").strip().lower()
	expires_at = None
	
	if expires_text not in ["нет", "no", "n"]:
		try:
			msk_timezone = timezone(timedelta(hours=3))
			if " " in expires_text:
				date_part, time_part = expires_text.split(" ", 1)
				day, month, year = map(int, date_part.split("."))
				hour, minute = map(int, time_part.split(":"))
			else:
				day, month, year = map(int, expires_text.split("."))
				hour, minute = 23, 59
			
			expires_at_msk = datetime(year, month, day, hour, minute, tzinfo=msk_timezone)
			expires_at = expires_at_msk.astimezone(timezone.utc)
		except (ValueError, AttributeError):
			await message.answer(
				"❌ Неверный формат даты. Используйте формат: ДД.ММ.ГГГГ ЧЧ:ММ или 'нет':",
				reply_markup=admin_promo_cancel_kb()
			)
			return
	
	data = await state.get_data()
	promo_code = data["promo_code"]
	
	async with async_session_maker() as session:
		promo = await session.get(PromoCode, promo_code)
		if not promo:
			await message.answer("❌ Промокод не найден", reply_markup=admin_promo_back_kb())
			await state.clear()
			return
		
		promo.expires_at = expires_at
		await session.commit()
	
	expires_str = _format_datetime(expires_at) if expires_at else "Не ограничено"
	await message.answer(
		f"✅ Дата окончания обновлена: {expires_str}",
		reply_markup=admin_promo_back_kb()
	)
	await state.clear()


@router.callback_query(F.data == "admin_cancel")
async def admin_promo_cancel(cb: CallbackQuery, state: FSMContext) -> None:
	"""Отменяет текущую операцию с промокодом."""
	await cb.answer("Операция отменена")
	await state.clear()
	await admin_promo_menu(cb)

