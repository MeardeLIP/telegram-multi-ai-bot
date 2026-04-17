from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.faceswap import faceswap_menu_kb
from app.bot.keyboards.main import main_menu_reply_kb
from app.bot.utils.tg import safe_edit_text
from app.config import get_settings
from app.db.session import async_session_maker
from app.services.billing import check_balance, debit_tokens, ensure_balance
from app.services.faceswap import swap_face


router = Router()
settings = get_settings()


FACE_SWAP_INTRO = (
	"🎭 FaceSwap · замена лиц на фотографиях\n\n"
	"Отправьте мне фото по очереди:\n\n"
	"1️⃣. Первая фотография с лицом, которое нужно заменить.\n"
	"2️⃣. Вторая фотография с вашим лицом.\n\n"
	"🏞 Если механизм выше тебе не нравится, то прикрепи две фотографии в одном сообщении.\n\n"
	"🧔 Убедись, что на двух фотографиях изображены реальные люди, иначе я не смогу сделать замену лица.\n\n"
	"🔹 Токенов хватит на 1 запрос. 1 запрос = 7,500 токенов."
)


class FaceSwapStates(StatesGroup):
	wait_first_photo = State()
	wait_second_photo = State()


async def _build_file_url(message: Message, file_id: str) -> str:
	file = await message.bot.get_file(file_id)
	return f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"


async def _extract_photo_url(message: Message) -> str | None:
	if not message.photo:
		return None
	photo = message.photo[-1]
	return await _build_file_url(message, photo.file_id)


class MessageWrapper:
	"""
	Обёртка для редактирования сообщения по ID.
	Используется когда нужно редактировать существующее сообщение, но у нас есть только его ID.
	"""
	def __init__(self, bot, chat_id, message_id):
		self.bot = bot
		self.chat = type('Chat', (), {'id': chat_id})()
		self.message_id = message_id
		
	async def edit_text(self, text: str, reply_markup=None):
		await self.bot.edit_message_text(
			chat_id=self.chat.id,
			message_id=self.message_id,
			text=text,
			reply_markup=reply_markup
		)
		
	async def delete(self):
		await self.bot.delete_message(
			chat_id=self.chat.id,
			message_id=self.message_id
		)


async def _process_faceswap(
	message: Message,
	state: FSMContext,
	source_url: str,
	target_url: str,
	waiting_msg: Message | None = None,
) -> None:
	"""
	Обрабатывает замену лица на фотографиях.
	
	Args:
		message: Сообщение от пользователя
		state: FSM контекст
		source_url: URL изображения, где нужно заменить лицо
		target_url: URL изображения с лицом для вставки
		waiting_msg: Сообщение, которое нужно редактировать (если есть)
	"""
	settings_local = get_settings()
	cost = settings_local.billing_faceswap_cost

	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[
						InlineKeyboardButton(
							text="💎 Оформить подписку", callback_data="menu_subscribe"
						)
					]
				]
			)
			if waiting_msg:
				try:
					await waiting_msg.edit_text(
						"❌ Недостаточно токенов для FaceSwap. Оформите подписку.",
						reply_markup=kb,
					)
				except Exception:
					await message.answer(
						"❌ Недостаточно токенов для FaceSwap. Оформите подписку.",
						reply_markup=kb,
					)
			else:
				await message.answer(
					"❌ Недостаточно токенов для FaceSwap. Оформите подписку.",
					reply_markup=kb,
				)
			await state.clear()
			return

	# Если waiting_msg не передан, создаём новое сообщение
	# MessageWrapper всегда является truthy, поэтому проверяем явно на None
	message_created_here = False
	if waiting_msg is None:
		waiting_msg = await message.answer("⏳ Произвожу замену лица на вашем фото...")
		message_created_here = True
	# Если waiting_msg передан (MessageWrapper или Message), используем его для редактирования

	# Редактируем на "Генерация может занять ~1 минуту"
	# Если сообщение только что создано, не редактируем его сразу на другой текст
	if not message_created_here:
		try:
			await safe_edit_text(
				waiting_msg, "🤔 Генерация может занять ~1 минуту."
			)
		except Exception:
			# Если редактирование не удалось, продолжаем с текущим сообщением
			pass

	# Выполняем замену лица
	try:
		image_bytes = await swap_face(source_url, target_url)
	except ValueError as exc:
		# Ошибки валидации (нет лица, несколько лиц и т.д.)
		error_message = str(exc).strip()
		logger.warning(f"Ошибка валидации FaceSwap: {error_message}")
		# Всегда редактируем существующее сообщение, не создаём новое
		if waiting_msg:
			try:
				await safe_edit_text(
					waiting_msg, f"❌ {error_message}", reply_markup=faceswap_menu_kb()
				)
			except Exception:
				# Если редактирование не удалось, удаляем старое и создаём новое
				try:
					await waiting_msg.delete()
				except Exception:
					pass
				await message.answer(f"❌ {error_message}", reply_markup=faceswap_menu_kb())
		else:
			await message.answer(f"❌ {error_message}", reply_markup=faceswap_menu_kb())
		await state.clear()
		return
	except Exception as exc:  # pragma: no cover - сеть/внешний API
		logger.exception(f"Ошибка FaceSwap: {exc}")
		# Всегда редактируем существующее сообщение, не создаём новое
		if waiting_msg:
			try:
				await safe_edit_text(
					waiting_msg,
					"❌ Не удалось выполнить FaceSwap. Попробуйте снова позже.",
					reply_markup=faceswap_menu_kb(),
				)
			except Exception:
				# Если редактирование не удалось, удаляем старое и создаём новое
				try:
					await waiting_msg.delete()
				except Exception:
					pass
				await message.answer(
					"❌ Не удалось выполнить FaceSwap. Попробуйте снова позже.",
					reply_markup=faceswap_menu_kb(),
				)
		else:
			await message.answer(
				"❌ Не удалось выполнить FaceSwap. Попробуйте снова позже.",
				reply_markup=faceswap_menu_kb(),
			)
		await state.clear()
		return

	# Списываем токены
	async with async_session_maker() as session:  # type: AsyncSession
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="faceswap",
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

	# Формируем имя файла с timestamp
	timestamp = datetime.now().strftime("%Y-%m-%d %H %M %S.%f")
	filename = f"faceswap_{timestamp}.jpeg"

	# Отправляем результат как фото
	# Делаем текст ссылкой на бота (HTML формат, так как parse_mode="HTML")
	bot_link_text = "ChatGPT 5 нейросеть ии | генерация фото и видео | FaceSwap | Telegram"
	caption = (
		"🎭 Заменил лицо на фото по вашему запросу.\n"
		"Фото 1 / 🖼️ Фото 2\n"
		f'<a href="https://t.me/{bot_username}">{bot_link_text}</a>'
	)
	photo = BufferedInputFile(image_bytes, filename=filename)
	await message.answer_photo(photo, caption=caption, reply_markup=faceswap_menu_kb())

	# Отправляем файл с оригинальным качеством
	document = BufferedInputFile(image_bytes, filename=filename)
	await message.answer_document(
		document,
		caption="🖼️ Это оригинальный файл с изображением и не сжатым качеством.",
	)

	# Отправляем информацию о токенах с кнопкой "Перейти в Замену лиц"
	cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
	cost_kb = InlineKeyboardMarkup(
		inline_keyboard=[
			[InlineKeyboardButton(text="🎭 Перейти в Замену лиц", callback_data="menu_faceswap")]
		]
	)
	await message.answer(cost_msg, reply_markup=cost_kb)

	await state.clear()


@router.callback_query(F.data == "menu_faceswap")
async def faceswap_menu(cb: CallbackQuery, state: FSMContext) -> None:
	await cb.answer()
	await state.clear()
	await state.update_data(
		first_photo_url=None, album_group=None, album_urls=[], waiting_msg_id=None
	)
	await cb.message.edit_text(FACE_SWAP_INTRO, reply_markup=faceswap_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки
	await state.set_state(FaceSwapStates.wait_first_photo)


@router.callback_query(F.data == "faceswap_cancel")
async def faceswap_cancel(cb: CallbackQuery, state: FSMContext) -> None:
	await cb.answer("Отменено")
	await state.clear()
	await cb.message.edit_text(
		"❌ FaceSwap отменён. Выберите действие в главном меню.",
		reply_markup=faceswap_menu_kb(),
	)


@router.message(FaceSwapStates.wait_first_photo, F.photo)
async def faceswap_first_photo(message: Message, state: FSMContext) -> None:
	data = await state.get_data()
	album_group = data.get("album_group")
	current_group = message.media_group_id

	photo_url = await _extract_photo_url(message)
	if not photo_url:
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова."
		)
		return

	# Поддержка медиа-альбомов (две фотографии в одном сообщении)
	if current_group:
		if album_group and album_group != current_group:
			# Если пришёл новый альбом, сбрасываем предыдущий
			waiting_msg = await message.answer("⏳ Произвожу замену лица на вашем фото...")
			await state.update_data(
				album_group=current_group,
				album_urls=[photo_url],
				waiting_msg_id=waiting_msg.message_id,
			)
		else:
			urls = data.get("album_urls", [])
			urls.append(photo_url)
			
			# Получаем существующее сообщение ожидания или создаём новое
			waiting_msg_id = data.get("waiting_msg_id")
			waiting_msg = None
			if waiting_msg_id:
				# Создаём обёртку для редактирования существующего сообщения
				waiting_msg = MessageWrapper(message.bot, message.chat.id, waiting_msg_id)
			else:
				# Если сообщения нет, создаём новое
				waiting_msg = await message.answer("⏳ Произвожу замену лица на вашем фото...")
				await state.update_data(waiting_msg_id=waiting_msg.message_id)
			
			await state.update_data(
				album_group=current_group,
				album_urls=urls,
			)

			if len(urls) == 2:
				await _process_faceswap(message, state, urls[0], urls[1], waiting_msg)
				return
			if len(urls) > 2:
				try:
					await waiting_msg.delete()
				except Exception:
					pass
				await message.answer(
					"❌ Для FaceSwap нужны ровно две фотографии.", reply_markup=faceswap_menu_kb()
				)
				await state.clear()
				return
			# Ждём вторую фотографию альбома
			return
	else:
		# Отправляем сообщение ожидания
		waiting_msg = await message.answer("⏳ Произвожу замену лица на вашем фото...")
		await state.update_data(
			first_photo_url=photo_url, waiting_msg_id=waiting_msg.message_id
		)
		await state.set_state(FaceSwapStates.wait_second_photo)
		# Не отправляем дополнительное сообщение, так как уже есть waiting_msg


@router.message(FaceSwapStates.wait_second_photo, F.photo)
async def faceswap_second_photo(message: Message, state: FSMContext) -> None:
	photo_url = await _extract_photo_url(message)
	if not photo_url:
		await message.answer(
			"❌ Не удалось получить фотографию. Попробуйте отправить снова."
		)
		return

	data = await state.get_data()
	first_photo_url = data.get("first_photo_url")
	if not first_photo_url:
		await message.answer(
			"❌ Не найдена первая фотография. Начните заново.",
			reply_markup=faceswap_menu_kb(),
		)
		await state.clear()
		return

	# Получаем сообщение ожидания из state
	# Сообщение должно быть создано при отправке первого фото
	waiting_msg_id = data.get("waiting_msg_id")
	if not waiting_msg_id:
		# Если по какой-то причине сообщения нет, это ошибка - не создаём новое
		# чтобы избежать дублирования. Просто создаём новое только в _process_faceswap если нужно
		waiting_msg = None
	else:
		# Создаём обёртку для редактирования существующего сообщения
		waiting_msg = MessageWrapper(message.bot, message.chat.id, waiting_msg_id)

	await _process_faceswap(message, state, first_photo_url, photo_url, waiting_msg)


@router.message(FaceSwapStates.wait_first_photo)
@router.message(FaceSwapStates.wait_second_photo)
async def faceswap_invalid_input(message: Message) -> None:
	await message.answer(
		"❌ Пожалуйста, отправьте фотографию. Текст или другие файлы не принимаются.",
		reply_markup=faceswap_menu_kb(),
	)

