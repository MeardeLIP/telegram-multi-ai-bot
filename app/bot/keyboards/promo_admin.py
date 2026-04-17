from datetime import datetime, timezone
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_promo_menu_kb() -> InlineKeyboardMarkup:
	"""Главное меню управления промокодами."""
	buttons = [
		[InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promo_create")],
		[InlineKeyboardButton(text="📋 Список промокодов", callback_data="admin_promo_list")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_admin")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_promo_back_kb() -> InlineKeyboardMarkup:
	"""Кнопка возврата в меню промокодов."""
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_promo_menu")]]
	)


def admin_promo_cancel_kb() -> InlineKeyboardMarkup:
	"""Кнопка отмены создания/редактирования промокода."""
	return InlineKeyboardMarkup(
		inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promo_menu")]]
	)


def admin_promo_list_kb(promocodes: list, page: int = 0, per_page: int = 10) -> InlineKeyboardMarkup:
	"""Клавиатура списка промокодов с пагинацией."""
	buttons = []
	
	# Показываем промокоды на текущей странице
	start_idx = page * per_page
	end_idx = start_idx + per_page
	promo_page = promocodes[start_idx:end_idx]
	
	for promo in promo_page:
		# Статус промокода
		status = "✅" if promo.active else "❌"
		if promo.expires_at:
			expires_at_utc = promo.expires_at.replace(tzinfo=timezone.utc) if promo.expires_at.tzinfo is None else promo.expires_at
			if expires_at_utc < datetime.now(timezone.utc):
				status = "⏰"
		if promo.used_count >= promo.max_uses:
			status = "🔒"
		
		max_uses_display = f"{promo.max_uses:,}" if promo.max_uses < 999999 else "∞"
		buttons.append([
			InlineKeyboardButton(
				text=f"{status} {promo.code} ({promo.used_count:,}/{max_uses_display})",
				callback_data=f"admin_promo_edit:{promo.code}"
			)
		])
	
	# Пагинация
	nav_buttons = []
	if page > 0:
		nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin_promo_list_page:{page-1}"))
	if end_idx < len(promocodes):
		nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"admin_promo_list_page:{page+1}"))
	
	if nav_buttons:
		buttons.append(nav_buttons)
	
	buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_promo_menu")])
	
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_promo_edit_kb(promo_code: str) -> InlineKeyboardMarkup:
	"""Клавиатура редактирования промокода."""
	buttons = [
		[InlineKeyboardButton(text="💰 Изменить бонус токенов", callback_data=f"admin_promo_edit_tokens:{promo_code}")],
		[InlineKeyboardButton(text="📊 Изменить процент скидки", callback_data=f"admin_promo_edit_discount:{promo_code}")],
		[InlineKeyboardButton(text="🔢 Изменить макс. использований", callback_data=f"admin_promo_edit_max_uses:{promo_code}")],
		[InlineKeyboardButton(text="📅 Изменить дату окончания", callback_data=f"admin_promo_edit_expires:{promo_code}")],
		[InlineKeyboardButton(text="🔄 Включить/Выключить", callback_data=f"admin_promo_toggle:{promo_code}")],
		[InlineKeyboardButton(text="🗑️ Удалить промокод", callback_data=f"admin_promo_delete:{promo_code}")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_promo_list")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)

