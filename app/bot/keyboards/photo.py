from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def photo_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела "Работа с фото".
	"""
	buttons = [
		[InlineKeyboardButton(text="🔍 Улучшить качество", callback_data="photo_enhance")],
		[InlineKeyboardButton(text="🪄 Заменить фон", callback_data="photo_replace_bg")],
		[InlineKeyboardButton(text="💧 Удалить фон", callback_data="photo_remove_bg")],
		[InlineKeyboardButton(text="🎬 Оживить фото", callback_data="photo_animate")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_tool_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для инструментов работы с фото.
	"""
	buttons = [
		[InlineKeyboardButton(text="✂️ Выбрать другой инструмент", callback_data="menu_photo")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_photo")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_enhance_result_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для результата улучшения фото.
	"""
	buttons = [
		[InlineKeyboardButton(text="🔍 Улучшить качество ещё раз", callback_data="photo_enhance")],
		[InlineKeyboardButton(text="✂️ Выбрать другой инструмент", callback_data="menu_photo")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_replace_bg_result_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для результата замены фона.
	"""
	buttons = [
		[InlineKeyboardButton(text="🪄 Заменить фон ещё раз", callback_data="photo_replace_bg")],
		[InlineKeyboardButton(text="✂️ Выбрать другой инструмент", callback_data="menu_photo")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_remove_bg_result_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для результата удаления фона.
	"""
	buttons = [
		[InlineKeyboardButton(text="💧 Удалить фон ещё раз", callback_data="photo_remove_bg")],
		[InlineKeyboardButton(text="✂️ Выбрать другой инструмент", callback_data="menu_photo")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_animate_mode_kb(current_mode: str = "standard", current_duration: int = 5) -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для выбора режима и длительности оживления фото.
	
	Args:
		current_mode: Текущий выбранный режим ("standard" или "pro")
		current_duration: Текущая выбранная длительность (5 или 10)
	"""
	# Кнопки режима (в один ряд горизонтально)
	mode_buttons = []
	if current_mode == "standard":
		mode_buttons.append(InlineKeyboardButton(text="Стандарт 720p ✓", callback_data="photo_animate_mode:standard"))
		mode_buttons.append(InlineKeyboardButton(text="Про 1080p", callback_data="photo_animate_mode:pro"))
	else:
		mode_buttons.append(InlineKeyboardButton(text="Стандарт 720p", callback_data="photo_animate_mode:standard"))
		mode_buttons.append(InlineKeyboardButton(text="Про 1080p ✓", callback_data="photo_animate_mode:pro"))
	
	# Кнопки длительности
	duration_buttons = []
	if current_duration == 5:
		duration_buttons.append(InlineKeyboardButton(text="5с ✓", callback_data="photo_animate_duration:5"))
		duration_buttons.append(InlineKeyboardButton(text="10с", callback_data="photo_animate_duration:10"))
	else:
		duration_buttons.append(InlineKeyboardButton(text="5с", callback_data="photo_animate_duration:5"))
		duration_buttons.append(InlineKeyboardButton(text="10с ✓", callback_data="photo_animate_duration:10"))
	
	buttons = [
		mode_buttons,
		duration_buttons,
		[InlineKeyboardButton(text="✅ Начать оживление", callback_data="photo_animate_start")],
		[InlineKeyboardButton(text="← Назад", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def photo_animate_result_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для результата оживления фото.
	"""
	buttons = [
		[InlineKeyboardButton(text="🎬 Оживить фото ещё раз", callback_data="menu_animate_photo")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)

