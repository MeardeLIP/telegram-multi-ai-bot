from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
	buttons = [
		[InlineKeyboardButton(text="💬 ChatGPT", callback_data="menu_chat")],
		[InlineKeyboardButton(text="💬 Диалоги", callback_data="menu_dialogs")],
		[InlineKeyboardButton(text="🎭 FaceSwap", callback_data="menu_faceswap")],
		[InlineKeyboardButton(text="🎤 Работа с аудио", callback_data="menu_audio")],
		[InlineKeyboardButton(text="✂️ Работа с фото", callback_data="menu_photo")],
		[InlineKeyboardButton(text="🎬 Оживить фото", callback_data="menu_animate_photo")],
		[InlineKeyboardButton(text="🖼️ Создать фото", callback_data="menu_create_photo")],
		[InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
		[InlineKeyboardButton(text="💎 Подписка", callback_data="menu_subscribe")],
	]
	if is_admin:
		buttons.insert(0, [InlineKeyboardButton(text="👑 Админка", callback_data="menu_admin")])
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def main_menu_reply_kb() -> ReplyKeyboardMarkup:
	"""Создаёт ReplyKeyboard с кнопкой возврата в главное меню."""
	return ReplyKeyboardMarkup(
		keyboard=[[KeyboardButton(text="← В главное меню")]],
		resize_keyboard=True,
		one_time_keyboard=False
	)


