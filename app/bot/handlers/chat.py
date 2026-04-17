from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.chat import chat_dialog_kb, chat_reply_kb
from app.db.session import async_session_maker
from app.db.models import User, Dialog, Message as MessageModel, Balance
from app.services.llm import chat_completion, vision_analyze
from app.services.audio import speech_to_text
from app.services.billing import estimate_text_tokens_rus, debit_tokens, check_balance
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.auth import is_admin
from app.bot.utils.notifications import notify_admins_new_user
from app.config import get_settings
import os
import tempfile
import asyncio


class ChatStates(StatesGroup):
	wait_message = State()


router = Router()


@router.callback_query(F.data == "menu_chat")
async def chat_begin(cb: CallbackQuery, state: FSMContext) -> None:
	# Отвечаем на callback_query сразу, чтобы избежать ошибки "query is too old"
	await cb.answer()
	
	await state.set_state(ChatStates.wait_message)
	
	# Инициализируем настройки диалога в FSM (по умолчанию история включена, показ затрат выключен)
	await state.update_data(history_enabled=True, costs_shown=False, dialog_id=None, kb_message_id=None)
	
	# Создаём или получаем активный диалог
	async with async_session_maker() as session:
		user_result = await session.execute(select(User).where(User.tg_id == cb.from_user.id))
		user = user_result.scalar_one_or_none()
		if not user:
			user = User(tg_id=cb.from_user.id, username=cb.from_user.username, ref_code=f"ref{cb.from_user.id}")
			session.add(user)
			await session.flush()
			# Отправляем уведомление администраторам о новом пользователе в фоне
			from loguru import logger
			logger.info(f"Обнаружен новый пользователь в chat: tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(cb.bot, user, cb.from_user.full_name))
		
		# Создаём новый активный диалог
		dialog = Dialog(user_id=user.id, model="gpt-5-mini", is_active=True)
		session.add(dialog)
		await session.flush()
		await session.commit()
		
		await state.update_data(dialog_id=dialog.id)
	
	text = (
		"💬 Диалог начался\n\n"
		"Для ввода используй:\n"
		"✏️ текст;\n"
		"🎤 голосовое сообщение;\n"
		"📷 фотографии (до 10 шт.);\n"
		"📎 файл: любой текстовый формат (txt, .py и т.п).\n\n"
		"Название: 🔥 GPT 5 Mini\n"
		"Модель: openai/gpt-5-mini\n"
		"История: сохраняется (📈)\n\n"
		"/end — завершит этот диалог\n"
		"/clear — очистит историю в этом диалоге"
	)
	
	await safe_edit_text(cb.message, text, reply_markup=chat_dialog_kb(history_enabled=True, costs_shown=False))
	# Показываем системную клавиатуру с кнопками управления (Reply Keyboard остается видимой)
	# Сохраняем ID сообщения для последующего удаления
	kb_msg = await cb.bot.send_message(cb.message.chat.id, "💬", reply_markup=chat_reply_kb())
	await state.update_data(kb_message_id=kb_msg.message_id)


async def _delete_message_after(bot, chat_id: int, message_id: int, delay: float) -> None:
	"""Удаляет сообщение через указанное время"""
	await asyncio.sleep(delay)
	try:
		await bot.delete_message(chat_id, message_id)
	except Exception:
		pass


@router.message(Command("end"), ChatStates.wait_message)
async def chat_end(message: Message, state: FSMContext) -> None:
	"""Завершение диалога"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	kb_message_id = data.get("kb_message_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			dialog = await session.get(Dialog, dialog_id)
			if dialog:
				dialog.is_active = False
				await session.commit()
	
	# Удаляем служебное сообщение с клавиатурой
	if kb_message_id:
		try:
			await message.bot.delete_message(message.chat.id, kb_message_id)
		except Exception:
			pass
	
	await state.clear()
	# Убираем системную клавиатуру и показываем главное меню
	from aiogram.types import ReplyKeyboardRemove
	# Отправляем одно сообщение с главным меню (Reply Keyboard скроется автоматически)
	await message.answer(
		"Добро пожаловать! Выберите раздел:",
		reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
	)


@router.message(Command("clear"), ChatStates.wait_message)
async def chat_clear(message: Message, state: FSMContext) -> None:
	"""Очистка истории диалога"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			await session.execute(delete(MessageModel).where(MessageModel.dialog_id == dialog_id))
			await session.commit()
	
	await message.answer("История диалога очищена.", reply_markup=chat_reply_kb())


@router.message(F.text == "🧹 Очистить историю", ChatStates.wait_message)
async def chat_clear_history_reply(message: Message, state: FSMContext) -> None:
	"""Очистка истории диалога через системную кнопку"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			await session.execute(delete(MessageModel).where(MessageModel.dialog_id == dialog_id))
			await session.commit()
	
	await message.answer("✅ История диалога очищена", reply_markup=chat_reply_kb())


@router.message(F.text == "🤖 Изменить модель", ChatStates.wait_message)
async def chat_change_model_reply(message: Message, state: FSMContext) -> None:
	"""Изменение модели через системную кнопку (пока заглушка)"""
	await message.answer("Функция изменения модели будет доступна в следующем обновлении", reply_markup=chat_reply_kb())


@router.message(F.text == "← В главное меню", ChatStates.wait_message)
async def chat_exit_to_main_reply(message: Message, state: FSMContext) -> None:
	"""Выход из чата в главное меню через системную кнопку"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	kb_message_id = data.get("kb_message_id")
	
	# Деактивируем диалог если есть
	if dialog_id:
		async with async_session_maker() as session:
			dialog = await session.get(Dialog, dialog_id)
			if dialog:
				dialog.is_active = False
				await session.commit()
	
	# Удаляем служебное сообщение с клавиатурой
	if kb_message_id:
		try:
			await message.bot.delete_message(message.chat.id, kb_message_id)
		except Exception:
			pass
	
	# Очищаем состояние
	await state.clear()
	
	# Убираем Reply Keyboard и показываем главное меню
	from aiogram.types import ReplyKeyboardRemove
	# Отправляем одно сообщение с главным меню (Reply Keyboard скроется автоматически)
	await message.answer(
		"Добро пожаловать! Выберите раздел:",
		reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
	)


@router.message(ChatStates.wait_message)
async def chat_message(message: Message, state: FSMContext) -> None:
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	history_enabled = data.get("history_enabled", True)
	costs_shown = data.get("costs_shown", False)
	
	user_content = ""
	user_text = ""
	
	# Обработка разных типов ввода
	if message.text:
		# Текстовое сообщение
		user_text = message.text
		user_content = user_text
	elif message.voice or message.audio:
		# Голосовое сообщение
		settings = get_settings()
		
		# Проверка баланса ПЕРЕД расшифровкой и обработкой
		duration = (message.voice or message.audio).duration or 60  # type: ignore[union-attr]
		minutes = max(1, round(duration / 60))
		stt_cost = settings.billing_stt_per_min * minutes
		# Примерная стоимость GPT-ответа с небольшим запасом (~300 символов)
		estimated_gpt_cost = estimate_text_tokens_rus(300)
		total_cost = stt_cost + estimated_gpt_cost
		
		# Проверяем баланс перед расшифровкой и обработкой (STT + GPT)
		async with async_session_maker() as session:
			has_balance = await check_balance(session, message.from_user.id, total_cost)
			if not has_balance:
				from app.bot.keyboards.subscribe import subscribe_menu_kb
				from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки аудио. Оформите подписку.", reply_markup=kb)
				return
		
		# Показываем промежуточное сообщение о расшифровке
		transcribing_msg = await message.answer("🎤 Расшифровываю аудио...")
		
		file_id = (message.voice or message.audio).file_id  # type: ignore[union-attr]
		file = await message.bot.get_file(file_id)
		
		tmpdir = tempfile.mkdtemp()
		in_path = os.path.join(tmpdir, "in.ogg")
		await message.bot.download_file(file.file_path, destination=in_path)
		
		user_text = await speech_to_text(in_path)
		user_content = user_text or "Расшифруй аудио"
		
		# Удаляем промежуточное сообщение о расшифровке
		try:
			await transcribing_msg.delete()
		except Exception:
			pass
		
		# Показываем исходный запрос
		if user_text:
			await message.answer(
				f"🎤 Голосовое сообщение\n\n"
				f"Исходный запрос:\n{user_text}"
			)
		
		# Списание за STT (после расшифровки, но перед GPT запросом)
		async with async_session_maker() as session:
			_, success = await debit_tokens(session, message.from_user.id, stt_cost, model="gpt-5-mini", mode="audio", success=True)
			if not success:
				from app.bot.keyboards.subscribe import subscribe_menu_kb
				from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки аудио. Оформите подписку.", reply_markup=kb)
				return
			await session.commit()
		
		# Продолжаем обработку как обычное текстовое сообщение
		# (код ниже обработает запрос через GPT, проверка баланса там уже учтет списанный STT)
	elif message.photo:
		# Фото (до 10 шт.)
		photos = message.photo
		if len(photos) > 10:
			photos = photos[:10]
		
		settings = get_settings()
		image_urls = []
		for photo in photos:
			file = await message.bot.get_file(photo.file_id)
			image_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
			image_urls.append(image_url)
		
		prompt = message.caption or "Опиши изображение"
		user_content = f"{prompt} [фото: {len(image_urls)} шт.]"
		user_text = prompt
		
		# Проверка баланса перед обработкой фото
		vision_tokens = settings.billing_vision_surcharge * len(image_urls)
		async with async_session_maker() as session:
			has_balance = await check_balance(session, message.from_user.id, vision_tokens)
			if not has_balance:
				from app.bot.keyboards.subscribe import subscribe_menu_kb
				from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
				return
		
		# Показываем промежуточное сообщение
		typing_msg = await message.answer("⏳ Пишу ответ, подождите пару секунд...")
		
		# Обработка фото через vision
		if len(image_urls) == 1:
			answer = await vision_analyze(image_urls[0], prompt)
		else:
			# Для нескольких фото обрабатываем первое
			answer = await vision_analyze(image_urls[0], f"{prompt} (всего фото: {len(image_urls)})")
		
		# Удаляем промежуточное сообщение
		try:
			await typing_msg.delete()
		except Exception:
			pass
		
		# Списание за vision
		remaining_tokens = 0
		async with async_session_maker() as session:
			bal, success = await debit_tokens(session, message.from_user.id, vision_tokens, model="gpt-5-mini", mode="vision", success=True)
			if not success:
				from app.bot.keyboards.subscribe import subscribe_menu_kb
				from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
				return
			
			remaining_tokens = bal.tokens or 0
			await session.commit()
		
		# Отправляем ответ GPT
		await message.answer(answer)
		
		# Показываем затраты отдельным сообщением если включено
		if costs_shown:
			def _format_tokens(value: int) -> str:
				return f"{value:,}".replace(",", " ")
			cost_msg = f"💎 Запрос стоил {_format_tokens(vision_tokens)} токенов. Осталось {_format_tokens(remaining_tokens)} токенов."
			await message.answer(cost_msg)
		return
	elif message.document:
		# Файл - показываем сообщение о платной подписке
		from app.bot.keyboards.subscribe import subscribe_menu_kb
		text = (
			"📁 Чтение документов доступно только платным подписчикам нашего бота. "
			"Вы можете купить подписку и воспользоваться этой функцией."
		)
		kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
		await message.answer(text, reply_markup=kb)
		return
	else:
		await message.answer("Поддерживаются только текст, голос, фото и файлы")
		return
	
	# Получаем историю диалога если включена
	messages_for_gpt = []
	if history_enabled and dialog_id:
		async with async_session_maker() as session:
			history_messages = await session.execute(
				select(MessageModel)
				.where(MessageModel.dialog_id == dialog_id)
				.order_by(MessageModel.created_at.desc())
				.limit(6)
			)
			history = history_messages.scalars().all()
			# Переворачиваем для правильного порядка
			for msg in reversed(history):
				messages_for_gpt.append({"role": msg.role, "content": msg.content})
	
	# Добавляем текущее сообщение
	messages_for_gpt.append({"role": "user", "content": user_content})
	
	# Оцениваем примерную стоимость запроса: фактическая длина запроса + небольшой запас на ответ
	request_length = max(len(user_text), 1)
	estimated_tokens = estimate_text_tokens_rus(request_length + 200)
	
	# Проверяем баланс перед выполнением запроса к GPT
	async with async_session_maker() as session:
		has_balance = await check_balance(session, message.from_user.id, estimated_tokens)
		if not has_balance:
			from app.bot.keyboards.subscribe import subscribe_menu_kb
			from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки запроса. Оформите подписку.", reply_markup=kb)
			return
	
	# Показываем промежуточное сообщение "Пишу ответ..."
	typing_msg = await message.answer("⏳ Пишу ответ, подождите пару секунд...")
	
	# Получаем ответ от GPT
	answer = await chat_completion(messages_for_gpt, model="gpt-5-mini")
	
	# Удаляем промежуточное сообщение
	try:
		await typing_msg.delete()
	except Exception:
		pass
	
	# Списание токенов (фактическое количество)
	tokens = estimate_text_tokens_rus(max(len(user_text), 1) + len(answer))
	remaining_tokens = 0
	async with async_session_maker() as session:
		bal, success = await debit_tokens(session, message.from_user.id, tokens, model="gpt-5-mini", mode="text", success=True)
		if not success:
			# Это не должно произойти, так как мы проверили баланс выше, но на всякий случай
			from app.bot.keyboards.subscribe import subscribe_menu_kb
			from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки запроса. Оформите подписку.", reply_markup=kb)
			return
		
		remaining_tokens = bal.tokens or 0
		
		# Сохраняем в историю если включена
		if history_enabled and dialog_id:
			# Сохраняем пользовательское сообщение
			user_msg = MessageModel(
				dialog_id=dialog_id,
				role="user",
				content=user_content,
				tokens_in=tokens // 2,  # Примерное разделение
			)
			session.add(user_msg)
			
			# Сохраняем ответ бота
			bot_msg = MessageModel(
				dialog_id=dialog_id,
				role="assistant",
				content=answer,
				tokens_out=tokens // 2,
			)
			session.add(bot_msg)
		
		await session.commit()
	
	# Отправляем ответ GPT
	await message.answer(answer)
	
	# Показываем затраты отдельным сообщением если включено
	if costs_shown:
		def _format_tokens(value: int) -> str:
			return f"{value:,}".replace(",", " ")
		cost_msg = f"💎 Запрос стоил {_format_tokens(tokens)} токенов. Осталось {_format_tokens(remaining_tokens)} токенов."
		await message.answer(cost_msg)


@router.callback_query(F.data == "chat_toggle_history")
async def chat_toggle_history(cb: CallbackQuery, state: FSMContext) -> None:
	"""Переключение истории диалога"""
	await cb.answer(f"История {'включена' if not (await state.get_data()).get('history_enabled', True) else 'выключена'}")
	
	data = await state.get_data()
	history_enabled = not data.get("history_enabled", True)
	await state.update_data(history_enabled=history_enabled)
	
	costs_shown = data.get("costs_shown", False)
	await safe_edit_text(cb.message, cb.message.text, reply_markup=chat_dialog_kb(history_enabled=history_enabled, costs_shown=costs_shown))


@router.callback_query(F.data == "chat_toggle_costs")
async def chat_toggle_costs(cb: CallbackQuery, state: FSMContext) -> None:
	"""Переключение показа затрат"""
	await cb.answer(f"Показ затрат {'включен' if not (await state.get_data()).get('costs_shown', False) else 'отключен'}")
	
	data = await state.get_data()
	costs_shown = not data.get("costs_shown", False)
	await state.update_data(costs_shown=costs_shown)
	
	history_enabled = data.get("history_enabled", True)
	await safe_edit_text(cb.message, cb.message.text, reply_markup=chat_dialog_kb(history_enabled=history_enabled, costs_shown=costs_shown))


@router.callback_query(F.data == "chat_clear_history")
async def chat_clear_history_cb(cb: CallbackQuery, state: FSMContext) -> None:
	"""Очистка истории диалога через кнопку"""
	await cb.answer("История диалога очищена")
	
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			await session.execute(delete(MessageModel).where(MessageModel.dialog_id == dialog_id))
			await session.commit()
	# Обновляем сообщение с кнопками
	history_enabled = data.get("history_enabled", True)
	costs_shown = data.get("costs_shown", False)
	if cb.message:
		await safe_edit_text(cb.message, cb.message.text or "", reply_markup=chat_dialog_kb(history_enabled=history_enabled, costs_shown=costs_shown))


@router.callback_query(F.data == "chat_change_model")
async def chat_change_model(cb: CallbackQuery, state: FSMContext) -> None:
	"""Изменение модели (пока заглушка)"""
	await cb.answer("Функция изменения модели будет доступна в следующем обновлении", show_alert=True)


