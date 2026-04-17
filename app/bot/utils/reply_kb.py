"""
Утилита для отправки ReplyKeyboard с автоматическим удалением сообщения.
ReplyKeyboard останется видимой даже после удаления сообщения.
"""
import asyncio
from aiogram.types import ReplyKeyboardMarkup, Message
from aiogram import Bot


async def send_reply_kb_and_delete(
	bot: Bot,
	chat_id: int,
	reply_markup: ReplyKeyboardMarkup
) -> None:
	"""
	Отправляет сообщение с ReplyKeyboard и сразу удаляет его.
	ReplyKeyboard останется видимой даже после удаления сообщения.
	
	Args:
		bot: Экземпляр бота
		chat_id: ID чата
		reply_markup: ReplyKeyboardMarkup для отправки
	"""
	# Отправляем сообщение с минимальным текстом и ReplyKeyboard
	kb_msg = await bot.send_message(chat_id, "•", reply_markup=reply_markup)
	# Удаляем сообщение сразу - ReplyKeyboard останется видимой
	try:
		await asyncio.sleep(0.1)  # Небольшая задержка для гарантии отправки
		await kb_msg.delete()
	except Exception:
		pass

