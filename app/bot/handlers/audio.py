import os
import tempfile
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, BufferedInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.audio import audio_menu_kb, tts_menu_kb, tts_voice_select_kb, transcribe_menu_kb
from app.bot.keyboards.main import main_menu_kb, main_menu_reply_kb
from app.db.session import async_session_maker
from app.services.audio import speech_to_text, text_to_speech
from app.services.billing import debit_tokens, check_balance, ensure_balance
from app.config import get_settings

router = Router()
settings = get_settings()


AUDIO_MENU_INTRO = (
	"🎤 Работа с аудио\n\n"
	"ℹ️ Выберите нейросеть для работы с аудио по кнопке ниже. "
	"После выбора – можете сразу отправлять запрос."
)

TTS_INTRO_TEMPLATE = (
	"🔊 Озвучка текста\n\n"
	"Отправьте мне текст, который нужно озвучить: можете поэкспериментировать с голосами.\n\n"
	"⚙️ Параметры\n"
	"Голос: {voice_name} {emoji}\n\n"
	"💎 Токенов хватит на {chars_available} символов озвучки текста. 1 символ = 10 токена"
)

TRANSCRIBE_INTRO = (
	"🎤 Расшифровка голоса\n\n"
	"Отправьте мне голосовое сообщение или аудиофайл для расшифровки.\n\n"
	"💎 Стоимость: 900 токенов за минуту аудио"
)


class TTSStates(StatesGroup):
	wait_text = State()


class TranscribeStates(StatesGroup):
	wait_voice = State()


# Маппинг голосов для отображения
VOICE_NAMES = {
	"alloy": ("Аллой", "👱‍♀️"),
	"echo": ("Эхо", "👱‍♂️"),
	"fable": ("Фэйбл", "😐"),
	"onyx": ("Оникс", "😐"),
	"nova": ("Нова", "👱‍♀️"),
	"shimmer": ("Шиммер", "👱‍♀️"),
}


@router.callback_query(F.data == "menu_audio")
async def audio_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Работа с аудио'."""
	await cb.answer()
	await state.clear()
	await cb.message.edit_text(AUDIO_MENU_INTRO, reply_markup=audio_menu_kb())
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.callback_query(F.data == "audio_tts")
async def tts_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Озвучка текста'."""
	await cb.answer()
	await state.clear()
	
	# Устанавливаем голос по умолчанию
	await state.update_data(voice="alloy")
	
	# Получаем баланс для расчета доступных символов
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		# 10 токенов за 1 символ
		chars_available = int(tokens / 10) if tokens > 0 else 0
	
	voice_name, emoji = VOICE_NAMES.get("alloy", ("Аллой", "👱‍♀️"))
	text = TTS_INTRO_TEMPLATE.format(
		voice_name=voice_name,
		emoji=emoji,
		chars_available=chars_available
	)
	
	await cb.message.edit_text(text, reply_markup=tts_menu_kb())
	await state.set_state(TTSStates.wait_text)


@router.callback_query(F.data == "tts_select_voice")
async def tts_select_voice_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню выбора голоса."""
	await cb.answer()
	
	data = await state.get_data()
	selected_voice = data.get("voice", "alloy")
	
	text = "🔊 Выберите голос которым будет озвучен ваш текст"
	await cb.message.edit_text(text, reply_markup=tts_voice_select_kb(selected_voice))


@router.callback_query(F.data.startswith("tts_voice_"))
async def tts_select_voice(cb: CallbackQuery, state: FSMContext) -> None:
	"""Обрабатывает выбор голоса."""
	await cb.answer()
	
	voice_id = cb.data.replace("tts_voice_", "")
	if voice_id not in VOICE_NAMES:
		voice_id = "alloy"
	
	await state.update_data(voice=voice_id)
	
	# Возвращаемся к меню TTS
	async with async_session_maker() as session:  # type: AsyncSession
		balance = await ensure_balance(session, cb.from_user.id)
		tokens = balance.tokens or 0
		# 10 токенов за 1 символ
		chars_available = int(tokens / 10) if tokens > 0 else 0
	
	voice_name, emoji = VOICE_NAMES.get(voice_id, ("Аллой", "👱‍♀️"))
	text = TTS_INTRO_TEMPLATE.format(
		voice_name=voice_name,
		emoji=emoji,
		chars_available=chars_available
	)
	
	await cb.message.edit_text(text, reply_markup=tts_menu_kb())


@router.message(TTSStates.wait_text, F.text)
async def tts_process_text(message: Message, state: FSMContext) -> None:
	"""Обрабатывает текст для озвучки."""
	text = message.text or ""
	if not text.strip():
		await message.answer("❌ Пожалуйста, отправьте текст для озвучки.")
		return
	
	# Получаем выбранный голос
	data = await state.get_data()
	voice = data.get("voice", "alloy")
	
	# Рассчитываем стоимость (10 токенов за 1 символ)
	text_length = len(text)
	cost = text_length * 10
	if cost == 0 and text_length > 0:
		cost = 10  # Минимум 10 токенов за 1 символ
	
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
				"❌ Недостаточно токенов для озвучки текста. Оформите подписку.",
				reply_markup=kb
			)
			return
		
		# Выполняем озвучку
		try:
			audio_bytes = await text_to_speech(text, voice=voice)
		except Exception as exc:
			logger.exception(f"Ошибка TTS: {exc}")
			await message.answer(
				"❌ Не удалось озвучить текст. Попробуйте снова позже.",
				reply_markup=tts_menu_kb()
			)
			return
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			cost,
			model="gpt-5",
			mode="tts",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Отправляем оригинальный файл как документ
		document_file = BufferedInputFile(audio_bytes, filename="tts_audio.mp3")
		await message.answer_document(
			document_file,
			caption="Это оригинальный файл с озвученным текстом.",
		)
		
		# Отправляем информацию о токенах с кнопкой возврата в меню озвучки
		cost_msg = f"🔹 Запрос стоил {cost:,} токенов. Осталось {remaining_tokens:,}"
		cost_kb = InlineKeyboardMarkup(
			inline_keyboard=[
				[InlineKeyboardButton(text="🔊 Озвучка текста", callback_data="audio_tts")]
			]
		)
		await message.answer(cost_msg, reply_markup=cost_kb)


@router.message(TTSStates.wait_text)
async def tts_invalid_input(message: Message) -> None:
	"""Обрабатывает неверный ввод в режиме TTS."""
	await message.answer(
		"❌ Пожалуйста, отправьте текст для озвучки.",
		reply_markup=tts_menu_kb()
	)


@router.callback_query(F.data == "audio_transcribe")
async def transcribe_menu(cb: CallbackQuery, state: FSMContext) -> None:
	"""Показывает меню 'Расшифровка голоса'."""
	await cb.answer()
	await state.clear()
	await cb.message.edit_text(TRANSCRIBE_INTRO, reply_markup=transcribe_menu_kb())
	await state.set_state(TranscribeStates.wait_voice)


@router.message(TranscribeStates.wait_voice, F.voice | F.audio)
async def transcribe_process_audio(message: Message, state: FSMContext) -> None:
	"""Обрабатывает голосовое сообщение для расшифровки."""
	settings_local = get_settings()
	
	# Оцениваем стоимость запроса
	duration = (message.voice or message.audio).duration or 60  # type: ignore[union-attr]
	minutes = max(1, round(duration / 60))
	stt_cost = settings_local.billing_stt_per_min * minutes
	
	# Проверяем баланс
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, stt_cost)
		if not has_balance:
			kb = InlineKeyboardMarkup(
				inline_keyboard=[
					[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]
				]
			)
			await message.answer(
				"❌ Недостаточно токенов для расшифровки голоса. Оформите подписку.",
				reply_markup=kb
			)
			return
		
		# Скачиваем файл
		file_id = (message.voice or message.audio).file_id  # type: ignore[union-attr]
		file = await message.bot.get_file(file_id)
		
		tmpdir = tempfile.mkdtemp()
		in_path = os.path.join(tmpdir, "audio.ogg")
		await message.bot.download_file(file.file_path, destination=in_path)
		
		# Выполняем расшифровку
		try:
			text = await speech_to_text(in_path)
		except Exception as exc:
			logger.exception(f"Ошибка STT: {exc}")
			await message.answer(
				"❌ Не удалось расшифровать аудио. Попробуйте снова позже.",
				reply_markup=transcribe_menu_kb()
			)
			return
		finally:
			# Удаляем временный файл
			try:
				os.remove(in_path)
				os.rmdir(tmpdir)
			except Exception:
				pass
		
		# Списываем токены
		balance, success = await debit_tokens(
			session,
			message.from_user.id,
			stt_cost,
			model="gpt-5",
			mode="stt",
			success=True,
		)
		if success:
			await session.commit()
			remaining_tokens = balance.tokens or 0
		else:
			await session.rollback()
			remaining_tokens = 0
		
		# Отправляем результат
		if text:
			await message.answer(f"📝 Расшифрованный текст:\n\n{text}", reply_markup=transcribe_menu_kb())
		else:
			await message.answer(
				"❌ Не удалось распознать текст в аудио.",
				reply_markup=transcribe_menu_kb()
			)
		
		# Отправляем информацию о токенах
		cost_msg = f"🔹 Расшифровка стоила {stt_cost:,} токенов. Осталось {remaining_tokens:,}"
		await message.answer(cost_msg)


@router.message(TranscribeStates.wait_voice)
async def transcribe_invalid_input(message: Message) -> None:
	"""Обрабатывает неверный ввод в режиме расшифровки."""
	await message.answer(
		"❌ Пожалуйста, отправьте голосовое сообщение или аудиофайл.",
		reply_markup=transcribe_menu_kb()
	)
