from aiogram import Router, F
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.subscribe import subscribe_menu_kb
from app.db.session import async_session_maker
from app.services.billing import apply_promocode
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.auth import is_admin


class PromoStates(StatesGroup):
	wait_code = State()


router = Router()


def promo_back_kb() -> InlineKeyboardMarkup:
	"""Клавиатура для возврата из активации промокода."""
	buttons = [
		[InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_subscribe")],
	]
	return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "menu_promo")
async def promo_begin(cb: CallbackQuery, state: FSMContext) -> None:
	"""Начинает процесс активации промокода."""
	await cb.answer()
	await state.set_state(PromoStates.wait_code)
	await safe_edit_text(
		cb.message,
		"🎟 Активация промокода\n\nВведите промокод для зачисления токенов.",
		reply_markup=promo_back_kb(),
	)


@router.message(PromoStates.wait_code)
async def promo_apply(message: Message, state: FSMContext) -> None:
	"""Обрабатывает введенный промокод."""
	code = (message.text or "").strip().upper()
	
	if not code:
		await message.answer(
			"❌ Промокод не может быть пустым. Введите промокод:",
			reply_markup=promo_back_kb(),
		)
		return
	
	async with async_session_maker() as session:  # type: AsyncSession
		added = await apply_promocode(session, tg_id=message.from_user.id, code=code)
		await session.commit()
	
	if added > 0:
		# Форматируем количество токенов
		tokens_str = f"{added:,}".replace(",", " ")
		await message.answer(
			f"✅ Промокод применён успешно!\n\n"
			f"Начислено: {tokens_str} токенов\n\n"
			f"💎 Ваш баланс пополнен.",
			reply_markup=promo_back_kb(),
		)
	else:
		await message.answer(
			"❌ Промокод недействителен или уже использован.\n\n"
			"Проверьте правильность ввода или обратитесь в поддержку.",
			reply_markup=promo_back_kb(),
		)
	await state.clear()


