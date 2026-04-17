from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def create_photo_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела "Создание фото".
	"""
	buttons = [
		[InlineKeyboardButton(text="✨ GPT Image", callback_data="create_photo_gpt_image")],
		[InlineKeyboardButton(text="🎭 Замена лиц", callback_data="menu_faceswap")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def gpt_image_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для меню GPT Image.
	"""
	buttons = [
		[InlineKeyboardButton(text="📐 Изменить формат", callback_data="gpt_image_format")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_create_photo")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def gpt_image_format_kb(selected_format: str = "1:1") -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для выбора формата GPT Image.
	
	Args:
		selected_format: Выбранный формат (1:1, 2:3, 3:2)
	"""
	formats = [
		("1:1", "gpt_image_format_1_1"),
		("2:3", "gpt_image_format_2_3"),
		("3:2", "gpt_image_format_3_2"),
	]
	
	buttons = []
	for fmt, callback_data in formats:
		prefix = "✅ " if fmt == selected_format else ""
		buttons.append(
			[InlineKeyboardButton(
				text=f"{prefix}{fmt}",
				callback_data=callback_data
			)]
		)
	
	buttons.append([InlineKeyboardButton(text="⬅️ Назад к GPT Image", callback_data="create_photo_gpt_image")])
	buttons.append([InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")])
	return InlineKeyboardMarkup(inline_keyboard=buttons)

