from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def faceswap_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела FaceSwap.
	"""
	buttons = [
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


