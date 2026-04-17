from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def dialogs_menu_kb() -> InlineKeyboardMarkup:
	"""
	Создаёт клавиатуру меню выбора категорий диалогов.
	"""
	buttons = [
		[InlineKeyboardButton(text="💬 Общение", callback_data="dialog_category:Общение")],
		[InlineKeyboardButton(text="🔍 Анализ текста", callback_data="dialog_category:Анализ текста")],
		[InlineKeyboardButton(text="🌐 Переводчик", callback_data="dialog_category:Переводчик")],
		[InlineKeyboardButton(text="📝 Генератор промптов", callback_data="dialog_category:Генератор промптов")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def dialog_settings_kb(history_enabled: bool = True, costs_shown: bool = False) -> InlineKeyboardMarkup:
	"""
	Создаёт клавиатуру для настроек диалога.
	history_enabled - включена ли история диалога
	costs_shown - показывать ли затраты токенов
	"""
	buttons = []
	
	# Кнопка истории
	if history_enabled:
		buttons.append([InlineKeyboardButton(text="🟢 История включена", callback_data="dialog_toggle_history")])
	else:
		buttons.append([InlineKeyboardButton(text="🔴 История выключена", callback_data="dialog_toggle_history")])
	
	# Кнопка показа затрат
	if costs_shown:
		buttons.append([InlineKeyboardButton(text="🟢 Показ затрат включен", callback_data="dialog_toggle_costs")])
	else:
		buttons.append([InlineKeyboardButton(text="🔴 Показ затрат отключен", callback_data="dialog_toggle_costs")])
	
	# Кнопка возврата
	buttons.append([InlineKeyboardButton(text="↩️ Назад к диалогам", callback_data="dialog_back")])
	buttons.append([InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")])

	return InlineKeyboardMarkup(inline_keyboard=buttons)


def dialog_reply_kb() -> ReplyKeyboardMarkup:
	"""
	Создаёт системную клавиатуру (Reply Keyboard) для диалога.
	Кнопки всегда видны внизу экрана и не отправляют сообщения в чат.
	"""
	buttons = [
		[KeyboardButton(text="🧹 Очистить историю"), KeyboardButton(text="❌ Закрыть диалог")],
	]
	return ReplyKeyboardMarkup(
		keyboard=buttons,
		resize_keyboard=True,
		one_time_keyboard=False,
		input_field_placeholder="Введите сообщение..."
	)

