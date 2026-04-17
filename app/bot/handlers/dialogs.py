from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from loguru import logger
import os
import tempfile
import asyncio

from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.dialogs import dialogs_menu_kb, dialog_settings_kb, dialog_reply_kb
from app.db.session import async_session_maker
from app.db.models import User, Dialog, Message as MessageModel, Balance
from app.services.llm import chat_completion, vision_analyze
from app.services.audio import speech_to_text
from app.services.billing import estimate_text_tokens_rus, debit_tokens, check_balance
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.notifications import notify_admins_new_user
from app.config import get_settings


class DialogStates(StatesGroup):
	wait_message = State()


# Системные промпты для категорий
DIALOG_PROMPTS = {
	"Общение": "Ты дружелюбный и полезный помощник. Отвечай на вопросы пользователя.",
	"Анализ текста": "Отправь мне любой свой текст на проверку, а я подскажу как его можно улучшить во всех возможных аспектах.",
	"Переводчик": (
		"Ты профессиональный переводчик. Определяй исходный язык автоматически. "
		"В первом ответе коротко уточни целевой язык (если пользователь его не указал). После уточнения делай переводы лаконично, 1–2 предложения, сохраняя смысл." 
	),
	"Генератор промптов": (
		"Ты эксперт по созданию промптов для генеративных моделей изображений. "
		"В первом ответе задай только один уточняющий вопрос (например, о теме сцены). После получения ответа задавай следующий вопрос по цепочке. "
		"Когда информации достаточно, сформируй две версии промпта (RU/EN), перечисли ключевые детали и стиль." 
	),
}

# Эмодзи для категорий
DIALOG_EMOJIS = {
	"Общение": "💬",
	"Анализ текста": "🔍",
	"Переводчик": "🌐",
	"Генератор промптов": "📝",
}

def get_dialog_intro(category: str, emoji: str) -> str:
	def build_intro(message: str) -> str:
		return (
			f"{emoji} Диалог начался\n\n"
			f"{message}\n\n"
			"Для ввода используй:\n"
			"✏️ текст;\n"
			"🎤 голосовое сообщение;\n"
			"📷 фотографии (до 10 шт.);\n"
			"📎 файл: любой текстовый формат (txt, .py и т.п).\n\n"
			f"Название: {emoji} {category}\n"
			"Модель: gpt-5-mini\n"
			"История: сохраняется (📈)\n\n"
			"/end — завершит этот диалог\n"
			"/clear — очистит историю в этом диалоге"
		)

	if category == "Переводчик":
		return build_intro("Пришли текст и укажи язык перевода. Если язык не назовёшь — предложу русский и английский.")
	if category == "Генератор промптов":
		return build_intro("Опиши идею будущего изображения в нескольких фразах. Я уточню недостающее и соберу промпт на русском и английском.")
	if category == "Анализ текста":
		return build_intro("Пришли свой текст — подскажу, что улучшить, и отмечу сильные места.")
	if category == "Общение":
		return build_intro("Привет! Я готов к диалогу. Задай вопрос, попроси совет или просто пообщайся.")
	return build_intro("Привет! Опиши задачу, а я помогу.")

router = Router()


@router.callback_query(F.data == "menu_dialogs")
async def dialogs_menu(cb: CallbackQuery) -> None:
	"""Меню выбора категорий диалогов"""
	await cb.answer()
	
	text = (
		"💬 Диалоги\n\n"
		"Диалоги нужны для хранения истории и роли (промпта). Каждый новый диалог — это отдельная ветка для общения с заранее заданной ролью с выбранной нейросетью. Вы можете выбрать подготовленный диалог или создать свой собственный."
	)
	
	await safe_edit_text(cb.message, text, reply_markup=dialogs_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	from app.bot.keyboards.main import main_menu_reply_kb
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data == "dialog_select_model")
async def dialog_select_model(cb: CallbackQuery) -> None:
	"""Заглушка для выбора модели"""
	await cb.answer("В следующем обновлении", show_alert=True)


@router.callback_query(F.data.startswith("dialog_category:"))
async def dialog_category_select(cb: CallbackQuery, state: FSMContext) -> None:
	"""Выбор категории диалога"""
	await cb.answer()
	
	category = cb.data.split(":", 1)[1]
	
	# Проверяем, реализована ли категория
	if category not in DIALOG_PROMPTS or DIALOG_PROMPTS[category] is None:
		await cb.answer("Эта категория будет доступна в следующем обновлении", show_alert=True)
		return
	
	await state.set_state(DialogStates.wait_message)
	
	# Инициализируем настройки диалога в FSM
	await state.update_data(
		history_enabled=True,
		costs_shown=False,
		dialog_id=None,
		kb_message_id=None,
		category=category
	)
	
	# Проверяем, есть ли активный диалог этой категории
	async with async_session_maker() as session:
		user_result = await session.execute(select(User).where(User.tg_id == cb.from_user.id))
		user = user_result.scalar_one_or_none()
		if not user:
			user = User(tg_id=cb.from_user.id, username=cb.from_user.username, ref_code=f"ref{cb.from_user.id}")
			session.add(user)
			await session.flush()
			# Отправляем уведомление администраторам о новом пользователе в фоне
			logger.info(f"Обнаружен новый пользователь в dialogs: tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(cb.bot, user, cb.from_user.full_name))
		
		# Ищем активный диалог этой категории
		dialog_result = await session.execute(
			select(Dialog).where(
				Dialog.user_id == user.id,
				Dialog.title == category,
				Dialog.is_active == True
			)
		)
		dialog = dialog_result.scalar_one_or_none()
		
		if not dialog:
			# Создаём новый диалог
			dialog = Dialog(
				user_id=user.id,
				title=category,
				model="gpt-5-mini",
				system_prompt=DIALOG_PROMPTS[category],
				is_active=True
			)
			session.add(dialog)
			await session.flush()
		
		await session.commit()
		await state.update_data(dialog_id=dialog.id)
	
	emoji = DIALOG_EMOJIS.get(category, "💬")
	text = get_dialog_intro(category, emoji)
	
	await safe_edit_text(cb.message, text, reply_markup=dialog_settings_kb(history_enabled=True, costs_shown=False))
	
	# Показываем системную клавиатуру с кнопками управления
	kb_msg = await cb.bot.send_message(cb.message.chat.id, "💬", reply_markup=dialog_reply_kb())
	await state.update_data(kb_message_id=kb_msg.message_id)


async def _delete_message_after(bot, chat_id: int, message_id: int, delay: float) -> None:
	"""Удаляет сообщение через указанное время"""
	await asyncio.sleep(delay)
	try:
		await bot.delete_message(chat_id, message_id)
	except Exception:
		pass


@router.message(Command("end"), DialogStates.wait_message)
async def dialog_end(message: Message, state: FSMContext) -> None:
	"""Завершение диалога"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	kb_message_id = data.get("kb_message_id")
	category = data.get("category", "Диалог")
	
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
	
	# Убираем Reply Keyboard
	from aiogram.types import ReplyKeyboardRemove
	
	emoji = DIALOG_EMOJIS.get(category, "💬")
	await message.answer(f"Диалог {emoji} {category} завершен", reply_markup=ReplyKeyboardRemove())
	
	# Возвращаем к меню выбора категорий
	text = (
		"💬 Диалоги\n\n"
		"Диалоги нужны для хранения истории и роли (промпта). Каждый новый диалог — это отдельная ветка для общения с заранее заданной ролью с выбранной нейросетью. Вы можете выбрать подготовленный диалог или создать свой собственный."
	)
	await message.answer(text, reply_markup=dialogs_menu_kb())


@router.message(Command("clear"), DialogStates.wait_message)
async def dialog_clear(message: Message, state: FSMContext) -> None:
	"""Очистка истории диалога"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			await session.execute(delete(MessageModel).where(MessageModel.dialog_id == dialog_id))
			await session.commit()
	
	await message.answer("История диалога очищена")


@router.message(F.text == "🧹 Очистить историю", DialogStates.wait_message)
async def dialog_clear_reply(message: Message, state: FSMContext) -> None:
	"""Очистка истории через Reply Keyboard"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	
	if dialog_id:
		async with async_session_maker() as session:
			await session.execute(delete(MessageModel).where(MessageModel.dialog_id == dialog_id))
			await session.commit()
	
	await message.answer("История диалога очищена")


@router.message(F.text == "❌ Закрыть диалог", DialogStates.wait_message)
async def dialog_close_reply(message: Message, state: FSMContext) -> None:
	"""Закрытие диалога через Reply Keyboard"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	kb_message_id = data.get("kb_message_id")
	category = data.get("category", "Диалог")
	
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
	
	# Убираем Reply Keyboard
	from aiogram.types import ReplyKeyboardRemove
	
	emoji = DIALOG_EMOJIS.get(category, "💬")
	await message.answer(f"Диалог {emoji} {category} завершен", reply_markup=ReplyKeyboardRemove())
	
	# Возвращаем к меню выбора категорий
	text = (
		"💬 Диалоги\n\n"
		"Диалоги нужны для хранения истории и роли (промпта). Каждый новый диалог — это отдельная ветка для общения с заранее заданной ролью с выбранной нейросетью. Вы можете выбрать подготовленный диалог или создать свой собственный."
	)
	await message.answer(text, reply_markup=dialogs_menu_kb())


@router.callback_query(F.data == "dialog_toggle_history")
async def dialog_toggle_history(cb: CallbackQuery, state: FSMContext) -> None:
	"""Переключение истории диалога"""
	await cb.answer()
	
	data = await state.get_data()
	history_enabled = not data.get("history_enabled", True)
	costs_shown = data.get("costs_shown", False)
	
	await state.update_data(history_enabled=history_enabled)
	await safe_edit_text(cb.message, cb.message.text or "", reply_markup=dialog_settings_kb(history_enabled=history_enabled, costs_shown=costs_shown))


@router.callback_query(F.data == "dialog_toggle_costs")
async def dialog_toggle_costs(cb: CallbackQuery, state: FSMContext) -> None:
	"""Переключение показа затрат"""
	await cb.answer()
	
	data = await state.get_data()
	history_enabled = data.get("history_enabled", True)
	costs_shown = not data.get("costs_shown", False)
	
	await state.update_data(costs_shown=costs_shown)
	await safe_edit_text(cb.message, cb.message.text or "", reply_markup=dialog_settings_kb(history_enabled=history_enabled, costs_shown=costs_shown))


@router.callback_query(F.data == "dialog_back")
async def dialog_back(cb: CallbackQuery, state: FSMContext) -> None:
	"""Возврат к списку диалогов из текущей категории"""
	await cb.answer()

	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	kb_message_id = data.get("kb_message_id")
	category = data.get("category", "Диалог")

	if dialog_id:
		async with async_session_maker() as session:
			dialog = await session.get(Dialog, dialog_id)
			if dialog:
				dialog.is_active = False
				await session.commit()

	if kb_message_id:
		try:
			await cb.bot.delete_message(cb.message.chat.id, kb_message_id)
		except Exception:
			pass

	await state.clear()

	text = (
		"💬 Диалоги\n\n"
		"Диалоги нужны для хранения истории и роли (промпта). Каждый новый диалог — это отдельная ветка для общения с заранее заданной ролью с выбранной нейросетью. Вы можете выбрать подготовленный диалог или создать свой собственный."
	)

	await safe_edit_text(cb.message, text, reply_markup=dialogs_menu_kb())


@router.message(DialogStates.wait_message)
async def dialog_message(message: Message, state: FSMContext) -> None:
	"""Обработка сообщений в диалоге"""
	data = await state.get_data()
	dialog_id = data.get("dialog_id")
	history_enabled = data.get("history_enabled", True)
	costs_shown = data.get("costs_shown", False)
	category = data.get("category", "Общение")
	
	if not dialog_id:
		await message.answer("Ошибка: диалог не найден")
		return
	
	settings = get_settings()
	user_content = ""
	user_text = ""
	
	# Обработка разных типов сообщений
	if message.text:
		# Текстовое сообщение
		user_content = message.text
		user_text = message.text
		category = data.get("category", "Общение")
		if category == "Генератор промптов" and looks_like_greeting(user_text):
			await message.answer("Привет! Опиши, что нужно сгенерировать: тему/сюжет, стиль и, если важно, модель. Начнём с основной идеи.")
			return
		if category == "Переводчик" and looks_like_greeting(user_text):
			await message.answer("Привет! Пришли текст и укажи язык перевода.")
			return
	elif message.voice or message.audio:
		# Голосовое сообщение или аудио
		duration = (message.voice or message.audio).duration or 60  # type: ignore[union-attr]
		minutes = max(1, round(duration / 60))
		stt_cost = settings.billing_stt_per_min * minutes
		estimated_gpt_cost = estimate_text_tokens_rus(300)
		total_cost = stt_cost + estimated_gpt_cost
		
		# Проверяем баланс
		async with async_session_maker() as session:
			has_balance = await check_balance(session, message.from_user.id, total_cost)
			if not has_balance:
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки аудио. Оформите подписку.", reply_markup=kb)
				return
		
		transcribing_msg = await message.answer("🎤 Расшифровываю аудио...")
		
		file_id = (message.voice or message.audio).file_id  # type: ignore[union-attr]
		file = await message.bot.get_file(file_id)
		
		tmpdir = tempfile.mkdtemp()
		in_path = os.path.join(tmpdir, "in.ogg")
		await message.bot.download_file(file.file_path, destination=in_path)
		
		user_text = await speech_to_text(in_path)
		user_content = user_text or "Расшифруй аудио"
		
		try:
			await transcribing_msg.delete()
		except Exception:
			pass
		
		if user_text:
			await message.answer(
				f"🎤 Голосовое сообщение\n\n"
				f"Исходный запрос:\n{user_text}"
			)
		
		# Списание за STT
		async with async_session_maker() as session:
			_, success = await debit_tokens(session, message.from_user.id, stt_cost, model="gpt-5-mini", mode="audio", success=True)
			if not success:
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки аудио. Оформите подписку.", reply_markup=kb)
				return
			await session.commit()
	
	elif message.photo:
		# Фото
		photos = message.photo
		if len(photos) > 10:
			photos = photos[:10]
		
		image_urls = []
		for photo in photos:
			file = await message.bot.get_file(photo.file_id)
			image_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
			image_urls.append(image_url)
		
		prompt = message.caption or "Опиши изображение"
		user_content = f"{prompt} [фото: {len(image_urls)} шт.]"
		user_text = prompt
		
		vision_tokens = settings.billing_vision_surcharge * len(image_urls)
		async with async_session_maker() as session:
			has_balance = await check_balance(session, message.from_user.id, vision_tokens)
			if not has_balance:
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
				return
		
		typing_msg = await message.answer("⏳ Пишу ответ, подождите пару секунд...")
		
		if len(image_urls) == 1:
			answer = await vision_analyze(image_urls[0], prompt)
		else:
			answer = await vision_analyze(image_urls[0], f"{prompt} (всего фото: {len(image_urls)})")
		
		try:
			await typing_msg.delete()
		except Exception:
			pass
		
		# Списание за vision
		async with async_session_maker() as session:
			_, success = await debit_tokens(session, message.from_user.id, vision_tokens, model="gpt-5-mini", mode="vision", success=True)
			if not success:
				kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
				await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
				return
			await session.commit()
		
		await message.answer(answer)
		
		# Показываем затраты если включено
		if costs_shown:
			async with async_session_maker() as session:
				from app.services.billing import ensure_balance
				bal = await ensure_balance(session, message.from_user.id)
				remaining = bal.tokens or 0
				await session.close()
			await message.answer(f"💎 Запрос стоил {vision_tokens} токенов. Осталось {remaining} токенов.")
		
		return
	
	elif message.document:
		# Файл
		file_ext = os.path.splitext(message.document.file_name or "")[1].lower() if message.document.file_name else ""
		supported_exts = {".txt", ".py", ".js", ".html", ".css", ".json", ".xml", ".md", ".csv"}
		
		if file_ext not in supported_exts:
			await message.answer("❌ Неподдерживаемый формат файла. Поддерживаются: txt, py, js, html, css, json, xml, md, csv")
			return
		
		# Проверяем, есть ли подписка (пока просто проверяем баланс)
		async with async_session_maker() as session:
			from app.services.billing import ensure_balance
			bal = await ensure_balance(session, message.from_user.id)
			has_subscription = (bal.tokens or 0) > 0
			await session.close()
		
		if not has_subscription:
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Обработка файлов доступна только для пользователей с активной подпиской.", reply_markup=kb)
			return
		
		# Скачиваем и читаем файл
		file = await message.bot.get_file(message.document.file_id)
		tmpdir = tempfile.mkdtemp()
		file_path = os.path.join(tmpdir, message.document.file_name or "file")
		await message.bot.download_file(file.file_path, destination=file_path)
		
		try:
			with open(file_path, "r", encoding="utf-8") as f:
				file_content = f.read()
			user_content = f"Файл {message.document.file_name}:\n\n{file_content}"
			user_text = file_content
		except Exception as e:
			await message.answer(f"❌ Ошибка чтения файла: {e}")
			return
		finally:
			try:
				os.remove(file_path)
				os.rmdir(tmpdir)
			except Exception:
				pass
	
	if not user_content:
		return
	
	# Инициализируем переменные для затрат
	actual_cost = 0
	remaining_tokens = 0
	
	# Получаем системный промпт для категории
	async with async_session_maker() as session:
		dialog = await session.get(Dialog, dialog_id)
		if not dialog:
			await message.answer("Ошибка: диалог не найден")
			return
		
		system_prompt = dialog.system_prompt
		
		# Формируем сообщения для GPT
		messages_list = []
		if system_prompt:
			messages_list.append({"role": "system", "content": system_prompt})
		
		# Загружаем историю если включена
		if history_enabled:
			history_result = await session.execute(
				select(MessageModel)
				.where(MessageModel.dialog_id == dialog_id)
				.order_by(MessageModel.created_at.desc())
				.limit(6)
			)
			history = history_result.scalars().all()
			# Переворачиваем, чтобы было в хронологическом порядке
			history = list(reversed(history))
			
			for msg in history:
				messages_list.append({"role": msg.role, "content": msg.content})
		
		messages_list.append({"role": "user", "content": user_content})
		
		# Оцениваем стоимость запроса (используем фактическую длину запроса, без искусственного завышения)
		request_length = max(len(user_content), 1)
		estimated_cost = estimate_text_tokens_rus(request_length)
		
		# Проверяем баланс
		has_balance = await check_balance(session, message.from_user.id, estimated_cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки запроса. Оформите подписку.", reply_markup=kb)
			return
		
		# Показываем промежуточное сообщение
		typing_msg = await message.answer("⏳ Пишу ответ, подождите пару секунд...")
		
		# Получаем ответ от GPT
		answer = await chat_completion(messages_list, model="gpt-5-mini")
		
		# Удаляем промежуточное сообщение
		try:
			await typing_msg.delete()
		except Exception:
			pass
		
		# Оцениваем фактическую стоимость
		actual_cost = estimate_text_tokens_rus(len(user_content) + len(answer))
		
		# Списываем токены
		bal, success = await debit_tokens(session, message.from_user.id, actual_cost, model="gpt-5-mini", mode="text", success=True)
		if not success:
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки запроса. Оформите подписку.", reply_markup=kb)
			return
		
		remaining_tokens = bal.tokens or 0
		
		# Сохраняем сообщения в историю если включена
		if history_enabled:
			user_msg = MessageModel(dialog_id=dialog_id, role="user", content=user_content)
			assistant_msg = MessageModel(dialog_id=dialog_id, role="assistant", content=answer)
			session.add(user_msg)
			session.add(assistant_msg)
		
		await session.commit()
	
	# Отправляем ответ
	await message.answer(answer)
	
	# Показываем затраты если включено
	if costs_shown:
		def _format_tokens(value: int) -> str:
			return f"{value:,}".replace(",", " ")
		cost_msg = f"💎 Запрос стоил {_format_tokens(actual_cost)} токенов. Осталось {_format_tokens(remaining_tokens)} токенов."
		await message.answer(cost_msg)


def looks_like_greeting(text: str) -> bool:
	normalized = text.strip().lower()
	if not normalized:
		return True
	greetings = [
		"привет",
		"здравствуй",
		"здравствуйте",
		"ку",
		"хай",
		"hi",
		"hello",
		"hey",
		"добрый день",
		"добрый вечер",
		"доброе утро",
		"салют",
		"прив",
	]
	return any(normalized.startswith(g) for g in greetings) or len(normalized) <= 4

