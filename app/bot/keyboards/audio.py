from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def audio_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела "Работа с аудио".
	"""
	buttons = [
		[InlineKeyboardButton(text="🎧 Расшифровка голоса", callback_data="audio_transcribe")],
		[InlineKeyboardButton(text="🔊 Озвучка текста", callback_data="audio_tts")],
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def tts_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела "Озвучка текста".
	"""
	buttons = [
		[InlineKeyboardButton(text="⚙️ Выбрать голос", callback_data="tts_select_voice")],
		[InlineKeyboardButton(text="🎤 Расшифровка голоса", callback_data="audio_transcribe")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_audio")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def tts_voice_select_kb(selected_voice: str = "alloy") -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для выбора голоса TTS.
	
	Args:
		selected_voice: Выбранный голос (alloy, echo, fable, onyx, nova, shimmer)
	"""
	voices = [
		("alloy", "Аллой", "👱‍♀️"),
		("echo", "Эхо", "👱‍♂️"),
		("fable", "Фэйбл", "😐"),
		("onyx", "Оникс", "😐"),
		("nova", "Нова", "👱‍♀️"),
		("shimmer", "Шиммер", "👱‍♀️"),
	]
	
	buttons = []
	for i in range(0, len(voices), 2):
		row = []
		for j in range(2):
			if i + j < len(voices):
				voice_id, voice_name, emoji = voices[i + j]
				prefix = "✅ " if voice_id == selected_voice else ""
				row.append(
					InlineKeyboardButton(
						text=f"{prefix}{voice_name} {emoji}",
						callback_data=f"tts_voice_{voice_id}"
					)
				)
		buttons.append(row)
	
	buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="audio_tts")])
	buttons.append([InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")])
	return InlineKeyboardMarkup(inline_keyboard=buttons)


def transcribe_menu_kb() -> InlineKeyboardMarkup:
	"""
	Инлайн-клавиатура для раздела "Расшифровка голоса".
	"""
	buttons = [
		[InlineKeyboardButton(text="🔊 Озвучка текста", callback_data="audio_tts")],
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_audio")],
		[InlineKeyboardButton(text="← В главное меню", callback_data="menu_main")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)

