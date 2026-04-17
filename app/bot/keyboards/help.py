from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def help_menu_kb(expanded: str | None = None) -> InlineKeyboardMarkup:
	"""
	Создаёт клавиатуру помощи с аккордеон-меню.
	expanded - какой раздел раскрыт (tokens, payments, chat, support, policy)
	Всегда показывает все кнопки, активная с "> Название <"
	"""
	buttons = []
	
	section_names = {
		"tokens": "💎 Токены",
		"payments": "💳 Платежи",
		"chat": "💬 ChatGPT",
		"support": "📬 Поддержка / сотрудничество",
		"policy": "📚 Политика хранения данных",
	}
	
	# Всегда показываем все кнопки
	for section_id, section_name in section_names.items():
		if expanded == section_id:
			# Активная кнопка с "> Название <"
			buttons.append([InlineKeyboardButton(text=f"> {section_name} <", callback_data=f"help_collapse:{section_id}")])
		else:
			# Обычная кнопка
			buttons.append([InlineKeyboardButton(text=section_name, callback_data=f"help_expand:{section_id}")])
	
	# Кнопка "В главное меню" всегда видна
	buttons.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")])
	
	return InlineKeyboardMarkup(inline_keyboard=buttons)

