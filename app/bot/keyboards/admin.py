from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_menu_kb() -> InlineKeyboardMarkup:
	buttons = [
		[InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
		[InlineKeyboardButton(text="📢 Отправить уведомление", callback_data="admin_broadcast")],
		[InlineKeyboardButton(text="➕ Пополнить счёт пользователя", callback_data="admin_topup")],
		[InlineKeyboardButton(text="💰 Проверить баланс", callback_data="admin_check_balance")],
		[InlineKeyboardButton(text="➖ Списать токены", callback_data="admin_deduct")],
		[InlineKeyboardButton(text="📊 Статистика запросов", callback_data="admin_usage_stats")],
		[InlineKeyboardButton(text="📜 История запросов", callback_data="admin_usage_history")],
		[InlineKeyboardButton(text="💳 Покупки подписок", callback_data="admin_subscriptions")],
		[InlineKeyboardButton(text="🎟 Управление промокодами", callback_data="admin_promo_menu")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_stats_back_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ Назад в админ-панель", callback_data="menu_admin")],
		]
	)


def admin_cancel_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
		]
	)


def admin_broadcast_confirm_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="✅ Отправить всем", callback_data="admin_broadcast_confirm")],
			[InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")],
		]
	)

