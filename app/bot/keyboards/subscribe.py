from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def subscribe_menu_kb() -> InlineKeyboardMarkup:
	buttons = [
		[InlineKeyboardButton(text="30 дней — 1,000,000 токенов", callback_data="plan:P30D_1M")],
		[InlineKeyboardButton(text="30 дней — 5,000,000 токенов", callback_data="plan:P30D_5M")],
		[InlineKeyboardButton(text="7 дней — 300,000 токенов", callback_data="plan:P7D_300K")],
		[InlineKeyboardButton(text="7 дней — 125,000 токенов", callback_data="plan:P7D_125K")],
		[InlineKeyboardButton(text="1 день — 50,000 токенов", callback_data="plan:P1D_50K")],
		[InlineKeyboardButton(text="🎟 Активировать промокод", callback_data="menu_promo")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_method_kb(plan_code: str) -> InlineKeyboardMarkup:
	"""Клавиатура выбора способа оплаты."""
	buttons = [
		[InlineKeyboardButton(text="💳 Карта, СБП и др.", callback_data=f"payment_method:card:{plan_code}")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_subscribe")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_invoice_kb(payment_url: str) -> InlineKeyboardMarkup:
	"""Клавиатура для перехода на страницу оплаты YooKassa."""
	buttons = [
		[InlineKeyboardButton(text="💸 Оплатить", url=payment_url)],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_subscribe")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


