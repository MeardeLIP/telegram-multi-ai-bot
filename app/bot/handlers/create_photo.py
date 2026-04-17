from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.create_photo import (
	create_photo_menu_kb, gpt_image_menu_kb, gpt_image_format_kb
)
from app.bot.keyboards.main import main_menu_kb, main_menu_reply_kb
from app.db.session import async_session_maker
from app.services.image_generation import generate_image, create_edit_prompt
from app.services.billing import debit_tokens, check_balance, ensure_balance
from app.config import get_settings

router = Router()
settings = get_settings()


CREATE_PHOTO_MENU_INTRO = (
	"🖼️ Создание фото\n\n"
	"ℹ️ Выберите нейросеть для генерации фото по кнопке ниже. "
	"После выбора – можете сразу отправлять запрос."
)

GPT_IMAGE_INTRO_TEMPLATE = (
	"✨ GPT Image 1 • лучший генератор изображений\n\n"
	"📖 Пишите запрос на любом языке:\n"
	"Эта модель понимает конкретно каждое ваше слово: на русском, на английском и любом языке;\n"
	"Попросите её, например, создать постер с приглашением на мероприятие (укажите всю информацию о нём) или крутых котов в очках (как люди в черном).\n\n"
	"📷 Можете прикрепить до 3 фото в одном сообщении с запросом:\n"
	"Прикрепите несколько фото с разными объектами и, например, попросите их соединить во что-то.\n\n"
	"🎨 Указывайте стиль генерации в запросе:\n"
	"Например: реалистичный стиль, стиль студии ghilbi (можете прикрепить свое фото) или любой другой;\n\n"
	"📐 Формат фото: {format}\n\n"
	"💎 Токенов хватит на {requests_available} запросов. 1 фото = 9500 токенов."
)

FORMAT_SELECT_INTRO = (
	"📐 Выберите формат создаваемого фото в GPT Image\n\n"
	"1:1: идеально подходит для профильных фото в соцсетях, таких как VK, Telegram и т.д\n\n"
	"2:3: хорошо подходит для печатных фотографий, но также может использоваться для пинов на Pinterest\n\n"
	"3:2: широко используемый формат для фотографий, подходит для постов в Telegram, VK, и др."
)


class GPTImageStates(StatesGroup):
	wait_prompt = State()


async def _build_file_url(message: Message, file_id: str) -> str:
	"""Строит URL файла для загрузки."""
	file = await message.bot.get_file(file_id)
	return f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"


async def _extract_photo_urls(message: Message) -> list[str]:
	"""Извлекает URL фотографий из сообщения (до 3)."""
	urls = []
	
	if message.photo:
		# Берем последнее (самое большое) фото из каждого сообщения
		photo = message.photo[-1]
		urls.append(await _build_file_url(message, photo.file_id))
	
	if message.document:
		mime_type = message.document.mime_type or ""
		if mime_type.startswith("image/"):
			urls.append(await _build_file_url(message, message.document.file_id))
	
	# Ограничиваем до 3 фото
	return urls[:3]




@router.callback_query(F.data == "menu_create_photo")
async def create_photo_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Создание фото'."""
	await cb.answer()
	await state.clear()
	from app.bot.utils.tg import safe_edit_text
	await safe_edit_text(cb.message, CREATE_PHOTO_MENU_INTRO, reply_markup=create_photo_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data == "create_photo_gpt_image")
async def gpt_image_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'GPT Image'."""
	await cb.answer()
	await state.clear()
	
	# Устанавливаем формат по умолчанию
	await state.update_data(format="1:1")
	
	# Получаем баланс для расчета доступных запросов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_gpt_image_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	text = GPT_IMAGE_INTRO_TEMPLATE.format(
		format="1:1",
		requests_available=requests_available
	)
	from app.bot.utils.tg import safe_edit_text
	await safe_edit_text(cb.message, text, reply_markup=gpt_image_menu_kb())
	await state.set_state(GPTImageStates.wait_prompt)


@router.callback_query(F.data == "gpt_image_format")
async def gpt_image_format_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню выбора формата."""
	await cb.answer()
	data = await state.get_data()
	current_format = data.get("format", "1:1")
	from app.bot.utils.tg import safe_edit_text
	await safe_edit_text(
		cb.message,
		FORMAT_SELECT_INTRO,
		reply_markup=gpt_image_format_kb(current_format)
	)


@router.callback_query(F.data.startswith("gpt_image_format_"))
async def gpt_image_set_format(cb: CallbackQuery, state: FSMContext) -> None:
	"""Устанавливает выбранный формат для GPT Image."""
	await cb.answer()
	
	# Извлекаем формат из callback_data
	format_map = {
		"gpt_image_format_1_1": "1:1",
		"gpt_image_format_2_3": "2:3",
		"gpt_image_format_3_2": "3:2",
	}
	selected_format = format_map.get(cb.data, "1:1")
	
	await state.update_data(format=selected_format)
	
	# Возвращаемся к меню GPT Image
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		cost = settings.billing_gpt_image_cost
		requests_available = int(tokens / cost) if tokens > 0 else 0
	
	text = GPT_IMAGE_INTRO_TEMPLATE.format(
		format=selected_format,
		requests_available=requests_available
	)
	from app.bot.utils.tg import safe_edit_text
	await safe_edit_text(cb.message, text, reply_markup=gpt_image_menu_kb())
	await state.set_state(GPTImageStates.wait_prompt)


@router.message(GPTImageStates.wait_prompt, F.text | F.photo | F.document)
async def gpt_image_process_request(message: Message, state: FSMContext) -> None:
	"""Обрабатывает запрос на генерацию изображения."""
	# Для медиа-групп: обрабатываем только первое сообщение, остальные пропускаем
	if message.media_group_id:
		data = await state.get_data()
		processed_groups = data.get("processed_media_groups", set())
		
		# Если эта группа уже обрабатывается, пропускаем
		if message.media_group_id in processed_groups:
			return
		
		# Помечаем группу как обрабатываемую сразу, чтобы не обработать дважды
		processed_groups.add(message.media_group_id)
		await state.update_data(processed_media_groups=processed_groups)
		
		# Собираем фото из текущего сообщения
		# Примечание: в медиа-группе каждое фото приходит отдельным сообщением
		# Для простоты обрабатываем только первое фото с caption (если есть)
		photo_urls = await _extract_photo_urls(message)
		prompt = message.caption or ""
	else:
		# Одиночное сообщение
		prompt = message.text or message.caption or ""
		photo_urls = await _extract_photo_urls(message)
	
	if not prompt.strip() and not photo_urls:
		await message.answer(
			"❌ Пожалуйста, отправьте текстовый запрос или фото с подписью.",
			reply_markup=gpt_image_menu_kb()
		)
		return
	
	# Если нет текста, но есть фото, используем дефолтный промпт
	if not prompt.strip():
		prompt = "Создай изображение на основе прикрепленных фото"
	
	# Получаем формат из FSM
	data = await state.get_data()
	format = data.get("format", "1:1")
	
	cost = settings.billing_gpt_image_cost
	
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
				"❌ Недостаточно токенов для генерации изображения. Оформите подписку.",
				reply_markup=kb
			)
			return
		
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("✨ Генерирую изображение...")
		
		# Генерируем изображение
		try:
			image_bytes = await generate_image(
				prompt=prompt,
				image_urls=photo_urls if photo_urls else None,
				format=format
			)
		except Exception as exc:
			logger.exception(f"Ошибка генерации изображения: {exc}")
			# Удаляем сообщение ожидания при ошибке
			try:
				await waiting_msg.delete()
			except Exception:
				pass
			await message.answer(
				"❌ Не удалось сгенерировать изображение. Попробуйте снова позже.",
				reply_markup=gpt_image_menu_kb()
			)
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="gpt_image",
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
		
		# Отправляем сгенерированное изображение
		photo_file = BufferedInputFile(image_bytes, filename="generated_image.png")
		await message.answer_photo(photo_file, caption=caption, parse_mode="HTML")
		
		# Отправляем документ с оригинальным качеством
		document_file = BufferedInputFile(image_bytes, filename="generated_image.png")
		await message.answer_document(
			document_file,
			caption="Это оригинальный файл с изображением и не сжатым качеством."
		)
		
		# Отправляем информацию о токенах
		cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
		cost_kb = InlineKeyboardMarkup(
			inline_keyboard=[
				[InlineKeyboardButton(text="✨ GPT Image", callback_data="create_photo_gpt_image")]
			]
		)
		await message.answer(cost_msg, reply_markup=cost_kb)
		
		await state.clear()


@router.message(GPTImageStates.wait_prompt)
async def gpt_image_invalid_input(message: Message) -> None:
	"""Обрабатывает неверный ввод в режиме GPT Image."""
	await message.answer(
		"❌ Пожалуйста, отправьте текстовый запрос или фото с подписью.",
		reply_markup=gpt_image_menu_kb()
	)

