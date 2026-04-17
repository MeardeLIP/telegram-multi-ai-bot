from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton


def chat_dialog_kb(history_enabled: bool = True, costs_shown: bool = False) -> InlineKeyboardMarkup:
	"""
	Создаёт клавиатуру для диалога с настройками.
	history_enabled - включена ли история диалога
	costs_shown - показывать ли затраты токенов
	"""
	buttons = []
	
	# Кнопка истории
	if history_enabled:
		buttons.append([InlineKeyboardButton(text="🟢 История включена", callback_data="chat_toggle_history")])
	else:
		buttons.append([InlineKeyboardButton(text="🔴 История выключена", callback_data="chat_toggle_history")])
	
	# Кнопка показа затрат
	if costs_shown:
		buttons.append([InlineKeyboardButton(text="🟢 Показ затрат включен", callback_data="chat_toggle_costs")])
	else:
		buttons.append([InlineKeyboardButton(text="🔴 Показ затрат отключен", callback_data="chat_toggle_costs")])
	
	# Кнопка в главное меню
	buttons.append([InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")])
	
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def chat_reply_kb() -> ReplyKeyboardMarkup:
	"""
	Создаёт системную клавиатуру (Reply Keyboard) для диалога.
	Кнопки всегда видны внизу экрана и не отправляют сообщения в чат.
	"""
	buttons = [
		[KeyboardButton(text="🧹 Очистить историю"), KeyboardButton(text="🤖 Изменить модель")],
		[KeyboardButton(text="← В главное меню")],
	]
	return ReplyKeyboardMarkup(
		keyboard=buttons,
		resize_keyboard=True,
		one_time_keyboard=False,
		input_field_placeholder="Введите сообщение..."
	)

