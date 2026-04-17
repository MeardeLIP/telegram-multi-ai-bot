from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_maker
from app.services.billing import debit_tokens, check_balance
from app.services.llm import vision_analyze
from app.config import get_settings
from app.bot.handlers.faceswap import FaceSwapStates

router = Router()


@router.message(lambda m: m.photo)
async def on_photo(message: Message, state: FSMContext) -> None:
	# Пропускаем фото, если пользователь в режиме FaceSwap или работы с фото
	current_state = await state.get_state()
	if current_state in (FaceSwapStates.wait_first_photo, FaceSwapStates.wait_second_photo):
		return  # Пусть faceswap_router обработает это фото
	
	# Проверяем состояния работы с фото и создания фото (импорт внутри функции, чтобы избежать циклического импорта)
	if current_state:
		state_name = str(current_state)
		if any(x in state_name for x in ["PhotoEnhanceStates", "PhotoReplaceBgStates", "PhotoRemoveBgStates", "PhotoAnimateStates", "GPTImageStates"]):
			return  # Пусть соответствующий роутер обработает это фото
	settings = get_settings()
	vision_cost = settings.billing_vision_surcharge
	
	# Проверяем баланс перед обработкой
	async with async_session_maker() as session:  # type: AsyncSession
		has_balance = await check_balance(session, message.from_user.id, vision_cost)
		if not has_balance:
			from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
			return
	
	photo = message.photo[-1]
	file = await message.bot.get_file(photo.file_id)
	image_url = f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"

	answer = await vision_analyze(image_url, prompt=message.caption or "Опиши изображение")

	# простое списание: надбавка за изображение
	async with async_session_maker() as session:  # type: AsyncSession
		_, success = await debit_tokens(session, message.from_user.id, vision_cost, model="gpt-5", mode="vision", success=True)
		if not success:
			from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
			kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💎 Оформить подписку", callback_data="menu_subscribe")]])
			await message.answer("❌ Недостаточно токенов для обработки фото. Оформите подписку.", reply_markup=kb)
			return
		await session.commit()

	await message.answer(answer)


