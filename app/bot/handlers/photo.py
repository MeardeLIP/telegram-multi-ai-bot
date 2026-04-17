import os
import tempfile
import httpx
import asyncio
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.photo import (
	photo_menu_kb,
	photo_tool_kb,
	photo_enhance_result_kb,
	photo_replace_bg_result_kb,
	photo_remove_bg_result_kb,
	photo_animate_mode_kb,
	photo_animate_result_kb,
)
from app.bot.keyboards.main import main_menu_kb, main_menu_reply_kb
from app.db.session import async_session_maker
from app.services.photo import enhance_photo, replace_background, remove_background
from app.services.kling import animate_photo
from app.services.billing import debit_tokens, check_balance, ensure_balance
from app.config import get_settings
from app.bot.utils.tg import safe_edit_text

router = Router()
settings = get_settings()


PHOTO_MENU_INTRO = (
	"✂️ Инструменты для работы с фото\n\n"
	"ℹ️ В этот раздел мы добавили инструменты, которые помогут вам эффективно работать с вашими фотографиями. "
	"Выберите интересующий вас инструмент по кнопке ниже."
)

ENHANCE_INTRO_TEMPLATE = (
	"🔍 Улучшение фото · максимальная детализация\n\n"
	"Отправьте мне фото и я улучшу его качество.\n\n"
	"Доступные форматы: Фото от Telegram или документ PNG, JPEG, WEBP, HEIC/HEIF.\n\n"
	"💎 Токенов хватит на {requests_available} запросов. 1 запрос = 4000 токенов."
)

REPLACE_BG_INTRO_TEMPLATE = (
	"🪄 Замена фона · создам приличный фон для ваших объектов\n\n"
	"Всё просто: отправьте мне фото с описанием того, что хотите видеть на новом фоне. "
	"Описание может быть на русском языке.\n\n"
	"Доступные форматы: Фото от Telegram или документ PNG, JPEG, WEBP, HEIC/HEIF.\n\n"
	"💎 Токенов хватит на {requests_available} запросов. 1 запрос = 11000 токенов."
)

REMOVE_BG_INTRO_TEMPLATE = (
	"💧 Удаление фона · оставлю только самое необходимое\n\n"
	"Отправьте мне фото и я удалю фон на нём, оставив всё самое важное.\n\n"
	"Доступные форматы: Фото от Telegram или документ PNG, JPEG, WEBP, HEIC/HEIF.\n\n"
	"💎 Токенов хватит на {requests_available} запросов. 1 запрос = 7500 токенов."
)

ANIMATE_INTRO_TEMPLATE = (
	"🎬 Оживить фото · создам видео из вашего фото\n\n"
	"Отправьте мне ваше фото и описание того, как нужно оживить фото.\n\n"
	"Процесс:\n"
	"1. Выберите режим и длительность\n"
	"2. Отправьте ваше фото\n"
	"3. (Опционально) Отправьте пример видео (например, где танцует мальчик)\n"
	"4. Напишите описание того, как нужно оживить фото\n\n"
	"💡 Вы можете отправить только фото и промпт, или добавить пример видео для более точного результата.\n\n"
	"💎 Токенов хватит на {requests_available} запросов. 1 запрос = 10 токенов.\n\n"
	"⏱ Примерное время ожидания готовности видео:\n"
	"• Стандарт (720p, 5с): до 5 минут\n"
	"• Стандарт (720p, 10с): до 7 минут\n"
	"• Про (1080p, 5с): до 7 минут\n"
	"• Про (1080p, 10с): до 10 минут\n\n"
	"💡 Видео высокого качества (1080p) и большей длительности требует больше вычислительных ресурсов, поэтому обработка занимает больше времени, но обеспечивает превосходный результат."
)

ANIMATE_MODE_SELECTION_TEMPLATE = (
	"🎬 Выберите режим и длительность (Kling)\n\n"
	"Текущий режим: {current_mode}\n"
	"Текущая длительность: {current_duration}\n\n"
	"Тарифы:\n"
	"• Стандарт — ⚡ 10 (5с), ⚡ 10 (10с)\n"
	"• Про — ⚡ 10 (5с), ⚡ 10 (10с)\n\n"
	"720p/1080p — это разрешение видео. Кнопки ниже.\n\n"
	"Видео для ваших фотографий можете скачать <a href=\"https://disk.yandex.ru/d/2lmCk5WlUjN6LQ\">здесь</a>, а так же можете использовать свои видео."
)


class PhotoEnhanceStates(StatesGroup):
	wait_photo = State()


class PhotoReplaceBgStates(StatesGroup):
	wait_photo = State()
	wait_description = State()


class PhotoRemoveBgStates(StatesGroup):
	wait_photo = State()


class PhotoAnimateStates(StatesGroup):
	wait_mode_duration = State()
	wait_photo = State()
	wait_reference_video = State()
	wait_description = State()


async def _build_file_url(message: Message, file_id: str) -> str:
	"""Строит URL файла для загрузки."""
	file = await message.bot.get_file(file_id)
	return f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"


async def _extract_photo_url(message: Message) -> str | None:
	"""Извлекает URL фотографии из сообщения."""
	if message.photo:
		photo = message.photo[-1]
		return await _build_file_url(message, photo.file_id)
	elif message.document:
		# Проверяем, что это изображение
		mime_type = message.document.mime_type or ""
		if mime_type.startswith("image/"):
			return await _build_file_url(message, message.document.file_id)
	return None


async def _extract_video_url(message: Message) -> str | None:
	"""Извлекает URL видео из сообщения."""
	if message.video:
		return await _build_file_url(message, message.video.file_id)
	elif message.document:
		# Проверяем, что это видео
		mime_type = message.document.mime_type or ""
		if mime_type.startswith("video/"):
			return await _build_file_url(message, message.document.file_id)
	return None


@router.callback_query(F.data == "menu_photo")
async def photo_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Работа с фото'."""
	await cb.answer()
	await state.clear()
	await cb.message.edit_text(PHOTO_MENU_INTRO, reply_markup=photo_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data == "photo_enhance")
async def photo_enhance_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Улучшение фото'."""
	await cb.answer()
	await state.clear()
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_enhance_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	text = ENHANCE_INTRO_TEMPLATE.format(requests_available=requests_available)
	await cb.message.edit_text(text, reply_markup=photo_tool_kb())
	await state.set_state(PhotoEnhanceStates.wait_photo)


@router.message(PhotoEnhanceStates.wait_photo, F.photo | F.document)
async def photo_enhance_process(message: Message, state: FSMContext) -> None:
	"""Обрабатывает фото для улучшения."""
	photo_url = await _extract_photo_url(message)
	if not photo_url:
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова.",
			reply_markup=photo_tool_kb()
		)
		return
	
	cost = settings.billing_photo_enhance_cost
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для улучшения фото. Оформите подписку.",
				reply_markup=kb
			)
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("🎨 Увеличиваю качество вашего фото...")
		
		# Выполняем улучшение
		try:
			image_bytes = await enhance_photo(photo_url)
		except Exception as exc:
			logger.exception(f"Ошибка улучшения фото: {exc}")
			# Удаляем сообщение ожидания при ошибке
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			await message.answer(
				"❌ Не удалось улучшить фото. Попробуйте снова позже.",
				reply_markup=photo_tool_kb()
			)
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="photo_enhance",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Удаляем сообщение ожидания
		try:
			await waiting_msg.delete()
		except Exception:
			pass
		
		# Получаем username бота для ссылки
		bot_info = await message.bot.me()
		bot_username = bot_info.username or "bot"
		
		# Формируем подпись-ссылку
		bot_link_text = f"ChatGPT 5 нейросеть ии | генерация фото и видео | {bot_username} | Telegram"
		caption = f'<a href="https://t.me/{bot_username}">{bot_link_text}</a>'
		
		# Отправляем улучшенное фото с подписью-ссылкой
		photo_file = BufferedInputFile(image_bytes, filename="enhanced_photo.jpg")
		await message.answer_photo(photo_file, caption=caption, parse_mode="HTML")
		
		# Отправляем документ с оригинальным качеством
		document_file = BufferedInputFile(image_bytes, filename="enhanced_photo.jpg")
		await message.answer_document(
			document_file,
			caption="Это оригинальный файл с изображением и не сжатым качеством."
		)
		
		# Отправляем информацию о токенах
		cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
		await message.answer(cost_msg, reply_markup=photo_enhance_result_kb())
		
		await state.clear()


@router.message(PhotoEnhanceStates.wait_photo)
async def photo_enhance_invalid_input(message: Message) -> None:
	"""Обрабатывает неверный ввод в режиме улучшения фото."""
	await message.answer(
		"❌ Пожалуйста, отправьте фотографию или документ с изображением.",
		reply_markup=photo_tool_kb()
	)


@router.callback_query(F.data == "photo_replace_bg")
async def photo_replace_bg_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Замена фона'."""
	await cb.answer()
	await state.clear()
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_replace_bg_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	text = REPLACE_BG_INTRO_TEMPLATE.format(requests_available=requests_available)
	await cb.message.edit_text(text, reply_markup=photo_tool_kb())
	await state.set_state(PhotoReplaceBgStates.wait_photo)


@router.message(PhotoReplaceBgStates.wait_photo, F.photo | F.document)
async def photo_replace_bg_process_photo(message: Message, state: FSMContext) -> None:
	"""Обрабатывает фото для замены фона."""
	photo_url = await _extract_photo_url(message)
	if not photo_url:
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова.",
			reply_markup=photo_tool_kb()
		)
		return
	
	# Сохраняем URL фото и проверяем, есть ли описание в подписи
	description = message.caption or ""
	
	if description:
		# Если описание есть в подписи, сразу обрабатываем
		await state.update_data(photo_url=photo_url, description=description)
		await _process_replace_background(message, state, photo_url, description)
	else:
		# Если описания нет, сохраняем фото и ждём описание
		await state.update_data(photo_url=photo_url)
		await state.set_state(PhotoReplaceBgStates.wait_description)
		await message.answer(
			"📝 Теперь отправьте описание того, что хотите видеть на новом фоне.",
			reply_markup=photo_tool_kb()
		)


@router.message(PhotoReplaceBgStates.wait_description, F.text)
async def photo_replace_bg_process_description(message: Message, state: FSMContext) -> None:
	"""Обрабатывает описание для замены фона."""
	data = await state.get_data()
	photo_url = data.get("photo_url")
	description = message.text or ""
	
	if not photo_url:
		await message.answer(
			"❌ Не найдено фотографии. Начните заново.",
			reply_markup=photo_tool_kb()
		)
		await state.clear()
		return
	
	if not description.strip():
		await message.answer(
			"❌ Пожалуйста, отправьте описание нового фона.",
			reply_markup=photo_tool_kb()
		)
		return
	
	await _process_replace_background(message, state, photo_url, description)


async def _process_replace_background(
	message: Message, state: FSMContext, photo_url: str, description: str
) -> None:
	"""Обрабатывает замену фона."""
	cost = settings.billing_photo_replace_bg_cost
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для замены фона. Оформите подписку.",
				reply_markup=kb
			)
			await state.clear()
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("🪄 Заменяю фон на вашем фото...")
		
		# Выполняем замену фона
		try:
			image_bytes = await replace_background(photo_url, description)
		except Exception as exc:
			logger.exception(f"Ошибка замены фона: {exc}")
			# Удаляем сообщение ожидания при ошибке
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			await message.answer(
				"❌ Не удалось заменить фон. Попробуйте снова позже.",
				reply_markup=photo_tool_kb()
			)
			await state.clear()
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="photo_replace_bg",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Удаляем сообщение ожидания
		try:
			await waiting_msg.delete()
		except Exception:
			pass
		
		# Получаем username бота для ссылки
		bot_info = await message.bot.me()
		bot_username = bot_info.username or "bot"
		
		# Формируем подпись-ссылку
		bot_link_text = f"ChatGPT 5 нейросеть ии | генерация фото и видео | {bot_username} | Telegram"
		caption = f'<a href="https://t.me/{bot_username}">{bot_link_text}</a>'
		
		# Отправляем результат с подписью-ссылкой
		photo_file = BufferedInputFile(image_bytes, filename="replaced_bg.jpg")
		await message.answer_photo(photo_file, caption=caption, parse_mode="HTML")
		
		# Отправляем документ с оригинальным качеством
		document_file = BufferedInputFile(image_bytes, filename="replaced_bg.jpg")
		await message.answer_document(
			document_file,
			caption="Это оригинальный файл с изображением и не сжатым качеством."
		)
		
		# Отправляем информацию о токенах
		cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
		await message.answer(cost_msg, reply_markup=photo_replace_bg_result_kb())
		
		await state.clear()


@router.message(PhotoReplaceBgStates.wait_description)
async def photo_replace_bg_invalid_description(message: Message) -> None:
	"""Обрабатывает неверный ввод при ожидании описания."""
	await message.answer(
		"❌ Пожалуйста, отправьте текстовое описание нового фона.",
		reply_markup=photo_tool_kb()
	)


@router.callback_query(F.data == "photo_remove_bg")
async def photo_remove_bg_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Удаление фона'."""
	await cb.answer()
	await state.clear()
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_remove_bg_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	text = REMOVE_BG_INTRO_TEMPLATE.format(requests_available=requests_available)
	await cb.message.edit_text(text, reply_markup=photo_tool_kb())
	await state.set_state(PhotoRemoveBgStates.wait_photo)


@router.message(PhotoRemoveBgStates.wait_photo, F.photo | F.document)
async def photo_remove_bg_process(message: Message, state: FSMContext) -> None:
	"""Обрабатывает фото для удаления фона."""
	photo_url = await _extract_photo_url(message)
	if not photo_url:
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова.",
			reply_markup=photo_tool_kb()
		)
		return
	
	cost = settings.billing_photo_remove_bg_cost
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для удаления фона. Оформите подписку.",
				reply_markup=kb
			)
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("💧 Удаляю фон на вашем фото...")
		
		# Выполняем удаление фона
		try:
			image_bytes = await remove_background(photo_url)
		except Exception as exc:
			logger.exception(f"Ошибка удаления фона: {exc}")
			# Удаляем сообщение ожидания при ошибке
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			await message.answer(
				"❌ Не удалось удалить фон. Попробуйте снова позже.",
				reply_markup=photo_tool_kb()
			)
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="photo_remove_bg",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Удаляем сообщение ожидания
		try:
			await waiting_msg.delete()
		except Exception:
			pass
		
		# Получаем username бота для ссылки
		bot_info = await message.bot.me()
		bot_username = bot_info.username or "bot"
		
		# Формируем подпись-ссылку
		bot_link_text = f"ChatGPT 5 нейросеть ии | генерация фото и видео | {bot_username} | Telegram"
		caption = f'<a href="https://t.me/{bot_username}">{bot_link_text}</a>'
		
		# Отправляем результат с подписью-ссылкой
		photo_file = BufferedInputFile(image_bytes, filename="removed_bg.jpg")
		await message.answer_photo(photo_file, caption=caption, parse_mode="HTML")
		
		# Отправляем документ с оригинальным качеством
		document_file = BufferedInputFile(image_bytes, filename="removed_bg.jpg")
		await message.answer_document(
			document_file,
			caption="Это оригинальный файл с изображением и не сжатым качеством."
		)
		
		# Отправляем информацию о токенах
		cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
		await message.answer(cost_msg, reply_markup=photo_remove_bg_result_kb())
		
		await state.clear()


@router.message(PhotoRemoveBgStates.wait_photo)
async def photo_remove_bg_invalid_input(message: Message) -> None:
	"""Обрабатывает неверный ввод в режиме удаления фона."""
	await message.answer(
		"❌ Пожалуйста, отправьте фотографию или документ с изображением.",
		reply_markup=photo_tool_kb()
	)


@router.callback_query(F.data == "menu_animate_photo")
async def menu_animate_photo(cb: CallbackQuery, state: FSMContext) -> None:
	"""Обработчик кнопки 'Оживить фото' из главного меню."""
	await cb.answer()
	await state.clear()
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_animate_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	# Устанавливаем значения по умолчанию
	await state.update_data(mode="standard", duration=5)
	
	# Объединяем вводный текст и меню выбора режима в одно сообщение
	intro_text = ANIMATE_INTRO_TEMPLATE.format(requests_available=requests_available)
	mode_text = ANIMATE_MODE_SELECTION_TEMPLATE.format(
		current_mode="Kling 2.1 / Стандарт — Kling 2.1 (720p)",
		current_duration="5c."
	)
	combined_text = f"{intro_text}\n\n{mode_text}"
	
	# Отредактируем сообщение с объединенным текстом и inline-клавиатурой
	await safe_edit_text(cb.message, combined_text, reply_markup=photo_animate_mode_kb("standard", 5), parse_mode="HTML")
	await state.set_state(PhotoAnimateStates.wait_mode_duration)


@router.callback_query(F.data == "photo_animate")
async def photo_animate_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню выбора режима и длительности для оживления фото (из раздела 'Работа с фото')."""
	await cb.answer()
	await state.clear()
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_animate_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	# Устанавливаем значения по умолчанию
	await state.update_data(mode="standard", duration=5)
	
	# Объединяем вводный текст и меню выбора режима в одно сообщение
	intro_text = ANIMATE_INTRO_TEMPLATE.format(requests_available=requests_available)
	mode_text = ANIMATE_MODE_SELECTION_TEMPLATE.format(
		current_mode="Kling 2.1 / Стандарт — Kling 2.1 (720p)",
		current_duration="5c."
	)
	combined_text = f"{intro_text}\n\n{mode_text}"
	
	# Отредактируем сообщение с объединенным текстом и inline-клавиатурой
	await safe_edit_text(cb.message, combined_text, reply_markup=photo_animate_mode_kb("standard", 5), parse_mode="HTML")
	await state.set_state(PhotoAnimateStates.wait_mode_duration)


@router.callback_query(F.data.startswith("photo_animate_mode:"))
async def photo_animate_mode_callback(cb: CallbackQuery, state: FSMContext) -> None:
	"""Обрабатывает выбор режима (Стандарт/Про)."""
	await cb.answer()
	mode = cb.data.split(":")[1]  # "standard" или "pro"
	
	data = await state.get_data()
	current_duration = data.get("duration", 5)
	
	await state.update_data(mode=mode)
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_animate_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	# Объединяем вводный текст и меню выбора режима в одно сообщение
	intro_text = ANIMATE_INTRO_TEMPLATE.format(requests_available=requests_available)
	mode_display = "Kling 2.1 / Стандарт — Kling 2.1 (720p)" if mode == "standard" else "Kling 2.1a / Про — Kling 2.1a (1080p)"
	mode_text = ANIMATE_MODE_SELECTION_TEMPLATE.format(
		current_mode=mode_display,
		current_duration=f"{current_duration}c."
	)
	combined_text = f"{intro_text}\n\n{mode_text}"
	
	# Отредактируем сообщение с объединенным текстом и inline-клавиатурой
	await safe_edit_text(cb.message, combined_text, reply_markup=photo_animate_mode_kb(mode, current_duration), parse_mode="HTML")


@router.callback_query(F.data.startswith("photo_animate_duration:"))
async def photo_animate_duration_callback(cb: CallbackQuery, state: FSMContext) -> None:
	"""Обрабатывает выбор длительности (5с/10с)."""
	await cb.answer()
	duration = int(cb.data.split(":")[1])  # 5 или 10
	
	data = await state.get_data()
	current_mode = data.get("mode", "standard")
	
	await state.update_data(duration=duration)
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_photo_animate_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	# Объединяем вводный текст и меню выбора режима в одно сообщение
	intro_text = ANIMATE_INTRO_TEMPLATE.format(requests_available=requests_available)
	mode_display = "Kling 2.1 / Стандарт — Kling 2.1 (720p)" if current_mode == "standard" else "Kling 2.1a / Про — Kling 2.1a (1080p)"
	mode_text = ANIMATE_MODE_SELECTION_TEMPLATE.format(
		current_mode=mode_display,
		current_duration=f"{duration}c."
	)
	combined_text = f"{intro_text}\n\n{mode_text}"
	
	# Отредактируем сообщение с объединенным текстом и inline-клавиатурой
	await safe_edit_text(cb.message, combined_text, reply_markup=photo_animate_mode_kb(current_mode, duration), parse_mode="HTML")




@router.message(PhotoAnimateStates.wait_photo, F.photo | F.document)
async def photo_animate_process_photo(message: Message, state: FSMContext) -> None:
	"""Обрабатывает загрузку фото для оживления."""
	logger.info(f"Обработчик фото вызван для пользователя {message.from_user.id}")
	# Проверяем, что это действительно изображение, а не видео
	if message.document:
		mime_type = message.document.mime_type or ""
		if mime_type.startswith("video/"):
			# Это видео, пропускаем этот обработчик
			return
	photo_url = await _extract_photo_url(message)
	if not photo_url:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова.",
			reply_markup=kb
		)
		return
	
	await state.update_data(photo_url=photo_url)
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"✅ Фото загружено.\n\n"
		"🎥 Отправьте пример видео (опционально) или напишите промпт для оживления фото.\n\n"
		"💡 Вы можете:\n"
		"• Отправить пример видео, затем промпт\n"
		"• Или сразу написать промпт для оживления",
		reply_markup=kb
	)
	# Оставляем состояние wait_photo, чтобы можно было принять и видео, и текст
	# Добавим обработчик текста в этом же состоянии


@router.message(PhotoAnimateStates.wait_photo, F.text)
async def photo_animate_process_prompt_after_photo(message: Message, state: FSMContext) -> None:
	"""Обрабатывает промпт после загрузки фото (без примера видео)."""
	logger.info(f"Обработчик промпта вызван для пользователя {message.from_user.id}, текст: {message.text}")
	description = message.text or ""
	
	if not description.strip():
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Пожалуйста, отправьте текстовое описание того, как нужно оживить фото.",
			reply_markup=kb
		)
		return
	
	# Сохраняем промпт и переходим к генерации (без reference_video_url)
	await state.update_data(description=description, reference_video_url=None)
	
	# Вызываем обработчик генерации напрямую
	data = await state.get_data()
	photo_url = data.get("photo_url")
	mode = data.get("mode", "standard")
	duration = data.get("duration", 5)
	
	logger.info(f"Данные состояния: photo_url={photo_url}, mode={mode}, duration={duration}, description={description}")
	
	if not photo_url:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Не найдено фото. Начните заново.",
			reply_markup=kb
		)
		await state.clear()
		return
	
	cost = settings.billing_photo_animate_cost
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для оживления фото. Оформите подписку.",
				reply_markup=kb
			)
			await state.clear()
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("✨ Оживляю фото...")
		
		# Генерируем видео
		try:
			video_url = await animate_photo(
				image_url=photo_url,
				reference_video_url=None,  # Без примера видео
				description=description,
				mode=mode,
				duration=duration
			)
		except Exception as exc:
			logger.exception(f"Ошибка оживления фото: {exc}")
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			await message.answer(
				f"❌ Не удалось оживить фото: {exc}. Попробуйте снова позже.",
			)
			await state.clear()
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="kling-v2",
			mode="photo_animate",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Удаляем сообщение ожидания
		try:
			await waiting_msg.delete()
		except Exception:
			pass
		
		# Загружаем видео
		async with httpx.AsyncClient(timeout=300.0) as http_client:
			response = await http_client.get(video_url)
			response.raise_for_status()
			video_bytes = response.content
		
		# Отправляем видео
		video_file = BufferedInputFile(video_bytes, filename="animated_video.mp4")
		await message.answer_video(video_file)
		
		# Отправляем информацию о токенах
		cost_msg = f"✅ Успешно. Списано: ⚡ {cost} токенов. Баланс: {remaining_tokens} токенов."
		await message.answer(cost_msg, reply_markup=photo_animate_result_kb())
		
		await state.clear()


@router.message(PhotoAnimateStates.wait_photo, F.video | F.document)
async def photo_animate_process_video_after_photo(message: Message, state: FSMContext) -> None:
	"""Обрабатывает загрузку примера видео после фото."""
	logger.info(f"Обработчик видео вызван для пользователя {message.from_user.id}")
	# Проверяем, что это действительно видео, а не изображение
	if message.document:
		mime_type = message.document.mime_type or ""
		if not mime_type.startswith("video/"):
			# Это не видео, пропускаем этот обработчик
			return
	video_url = await _extract_video_url(message)
	if not video_url:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Не удалось получить видео. Попробуйте отправить снова или напишите промпт для оживления.",
			reply_markup=kb
		)
		return
	
	await state.update_data(reference_video_url=video_url)
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"📝 Теперь напишите описание того, как нужно оживить фото (например, 'танец как мальчик').",
		reply_markup=kb
	)
	await state.set_state(PhotoAnimateStates.wait_description)


@router.message(PhotoAnimateStates.wait_reference_video, F.video | F.document)
async def photo_animate_process_video(message: Message, state: FSMContext) -> None:
	"""Обрабатывает загрузку примера видео."""
	video_url = await _extract_video_url(message)
	if not video_url:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Не удалось получить видео. Попробуйте отправить снова.",
			reply_markup=kb
		)
		return
	
	await state.update_data(reference_video_url=video_url)
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"📝 Теперь напишите описание того, как нужно оживить фото (например, 'танец как мальчик').",
		reply_markup=kb
	)
	await state.set_state(PhotoAnimateStates.wait_description)


@router.message(PhotoAnimateStates.wait_description, F.text)
async def photo_animate_process_description(message: Message, state: FSMContext) -> None:
	"""Обрабатывает текстовое описание и запускает генерацию видео."""
	description = message.text or ""
	
	if not description.strip():
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Пожалуйста, отправьте текстовое описание.",
			reply_markup=kb
		)
		return
	
	data = await state.get_data()
	photo_url = data.get("photo_url")
	reference_video_url = data.get("reference_video_url")  # Может быть None, если видео не отправляли
	mode = data.get("mode", "standard")
	duration = data.get("duration", 5)
	
	if not photo_url:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await message.answer(
			"❌ Не найдено фото. Начните заново.",
			reply_markup=kb
		)
		await state.clear()
		return
	
	cost = settings.billing_photo_animate_cost
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для оживления фото. Оформите подписку.",
				reply_markup=kb
			)
			await state.clear()
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("🎬 Оживляю ваше фото... Это может занять некоторое время.")
		
		# Флаг для остановки обновлений статуса
		status_update_stop = asyncio.Event()
		
		# Функция для периодического обновления статуса
		async def update_status_periodically():
			"""Обновляет сообщение о статусе каждые 30 секунд."""
			update_interval = 30  # Обновляем каждые 30 секунд
			elapsed = 0
			status_messages = [
				"🎬 Оживляю ваше фото... Это может занять некоторое время.",
				"⏳ Оживляю ваше фото... Обработка продолжается...",
				"🎥 Оживляю ваше фото... Генерация видео в процессе...",
				"✨ Оживляю ваше фото... Почти готово...",
			]
			message_index = 0
			
			while not status_update_stop.is_set():
				try:
					await asyncio.wait_for(status_update_stop.wait(), timeout=update_interval)
					break  # Если событие установлено, выходим
				except asyncio.TimeoutError:
					# Время обновления прошло, обновляем сообщение
					elapsed += update_interval
					message_index = (message_index + 1) % len(status_messages)
					
					try:
						status_text = (
							f"{status_messages[message_index]}\n"
							f"⏱ Прошло времени: {elapsed // 60}м {elapsed % 60}с"
						)
						await waiting_msg.edit_text(status_text)
					except Exception as e:
						# Игнорируем ошибки редактирования (сообщение может быть удалено)
						logger.debug(f"Не удалось обновить статус сообщения: {e}")
		
		# Запускаем фоновую задачу обновления статуса
		status_update_task = asyncio.create_task(update_status_periodically())
		
		# Выполняем оживление фото
		try:
			video_url = await animate_photo(
				image_url=photo_url,
				reference_video_url=reference_video_url,
				description=description,
				mode=mode,
				duration=duration
			)
		except Exception as exc:
			logger.exception(f"Ошибка оживления фото: {exc}")
			# Останавливаем обновления статуса
			status_update_stop.set()
			try:
				status_update_task.cancel()
				await status_update_task
			except Exception:
				pass
			# Удаляем сообщение ожидания при ошибке
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			kb = InlineKeyboardMarkup(inline_keyboard=[
				[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
			])
			await message.answer(
				f"❌ Не удалось оживить фото: {exc}. Попробуйте снова позже.",
				reply_markup=kb
			)
			await state.clear()
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="kling-v2",
			mode="photo_animate",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Останавливаем обновления статуса
		status_update_stop.set()
		try:
			status_update_task.cancel()
			await status_update_task
		except Exception:
			pass
		
		# Удаляем сообщение ожидания
		try:
			await waiting_msg.delete()
		except Exception:
			pass
		
		# Загружаем видео и отправляем пользователю
		try:
			async with httpx.AsyncClient(timeout=60.0) as http_client:
				video_response = await http_client.get(video_url)
				video_response.raise_for_status()
				video_bytes = video_response.content
			
			# Отправляем видео
			video_file = BufferedInputFile(video_bytes, filename="animated_video.mp4")
			await message.answer_video(video_file, caption="🎬 Ваше фото оживлено!")
			
			# Отправляем информацию о токенах
			cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
			await message.answer(cost_msg, reply_markup=photo_animate_result_kb())
			
		except Exception as exc:
			logger.exception(f"Ошибка загрузки или отправки видео: {exc}")
			# Если не удалось загрузить, отправляем ссылку
			await message.answer(
				f"✅ Видео готово! Скачайте по ссылке:\n{video_url}\n\n"
				f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}",
				reply_markup=photo_animate_result_kb()
			)
		
		await state.clear()


@router.message(PhotoAnimateStates.wait_photo)
async def photo_animate_invalid_photo(message: Message) -> None:
	"""Обрабатывает неверный ввод при ожидании фото."""
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"❌ Пожалуйста, отправьте фотографию или документ с изображением.",
		reply_markup=kb
	)


@router.message(PhotoAnimateStates.wait_reference_video)
async def photo_animate_invalid_video(message: Message) -> None:
	"""Обрабатывает неверный ввод при ожидании видео."""
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"❌ Пожалуйста, отправьте видео или документ с видео.",
		reply_markup=kb
	)


@router.message(PhotoAnimateStates.wait_description)
async def photo_animate_invalid_description(message: Message) -> None:
	"""Обрабатывает неверный ввод при ожидании описания."""
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await message.answer(
		"❌ Пожалуйста, отправьте текстовое описание того, как нужно оживить фото.",
		reply_markup=kb
	)


@router.callback_query(F.data == "photo_animate_start")
async def photo_animate_start(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс оживления фото после выбора режима и длительности."""
	await cb.answer()
	data = await state.get_data()
	mode = data.get("mode", "standard")
	duration = data.get("duration", 5)
	
	if not mode or not duration:
		kb = InlineKeyboardMarkup(inline_keyboard=[
			[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
		])
		await cb.message.answer("❌ Пожалуйста, выберите режим и длительность.", reply_markup=kb)
		return
	
	kb = InlineKeyboardMarkup(inline_keyboard=[
		[InlineKeyboardButton(text="⬅️ В главное меню", callback_data="menu_main")]
	])
	await cb.message.answer(
		"📸 Отправьте ваше фото, которое нужно оживить.",
		reply_markup=kb
	)
	await state.set_state(PhotoAnimateStates.wait_photo)

