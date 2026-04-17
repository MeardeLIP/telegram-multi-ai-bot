from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_menu_kb() -> InlineKeyboardMarkup:
	buttons = [
		[InlineKeyboardButton(text="🧾 Мои платежи", callback_data="profile_payments")],
		[InlineKeyboardButton(text="👥 Пригласить друга", callback_data="profile_ref")],
		[InlineKeyboardButton(text="❓ Помощь", callback_data="profile_help")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def payments_back_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_back")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")]
	])


def referral_kb(ref_link: str) -> InlineKeyboardMarkup:
	# Используем switch_inline_query - откроет диалог выбора чата для пересылки
	# Telegram автоматически добавляет @username бота, поэтому делаем текст понятным
	share_text = f"Присоединяйся к боту с GPT-5!\n\n{ref_link}"
	buttons = [
		[InlineKeyboardButton(text="🔗 Поделиться ссылкой", switch_inline_query=share_text)],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_back")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_help_back_kb() -> InlineKeyboardMarkup:
	return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="profile_back")]])

