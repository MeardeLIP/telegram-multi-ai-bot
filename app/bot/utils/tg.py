from typing import Union
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, InlineKeyboardMarkup, LinkPreviewOptions


async def safe_edit_text(
	message: Union[Message, object], 
	text: str, 
	reply_markup: InlineKeyboardMarkup | None = None,
	parse_mode: str | None = None,
	disable_link_preview: bool = False
) -> None:
	"""
	Безопасно редактирует сообщение. Если содержимое не изменилось — игнорируем ошибку Telegram.
	Поддерживает как объект Message, так и MessageWrapper.
	Автоматически определяет нужно ли использовать edit_text или edit_caption (для сообщений с фото).
	
	Args:
		disable_link_preview: Если True, отключает превью ссылок в сообщении
	"""
	try:
		# Настройка превью ссылок
		link_preview_options = LinkPreviewOptions(is_disabled=disable_link_preview) if disable_link_preview else None
		
		# Проверяем есть ли фото в сообщении
		has_photo = False
		if hasattr(message, 'photo') and message.photo:
			has_photo = True
		elif hasattr(message, 'message') and hasattr(message.message, 'photo') and message.message.photo:
			has_photo = True
		
		# Если сообщение с фото - используем edit_caption, иначе edit_text
		if has_photo:
			if parse_mode:
				await message.edit_caption(
					caption=text,
					reply_markup=reply_markup,
					parse_mode=parse_mode
				)
			else:
				await message.edit_caption(
					caption=text,
					reply_markup=reply_markup
				)
		else:
			# Вызываем edit_text - работает и для Message, и для MessageWrapper
			if parse_mode:
				await message.edit_text(
					text, 
					reply_markup=reply_markup, 
					parse_mode=parse_mode,
					link_preview_options=link_preview_options
				)
			else:
				await message.edit_text(
					text, 
					reply_markup=reply_markup,
					link_preview_options=link_preview_options
				)
	except TelegramBadRequest as e:
		# Например: "message is not modified", "there is no text in the message to edit" или "message to edit not found"
		# В таких случаях просто игнорируем
		error_str = str(e).lower()
		if "message is not modified" in error_str or "there is no text in the message to edit" in error_str or "message to edit not found" in error_str:
			return
		raise


