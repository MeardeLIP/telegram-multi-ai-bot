from aiogram import Router, F
from aiogram.types import CallbackQuery

from app.bot.keyboards.main import main_menu_kb, main_menu_reply_kb
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.auth import is_admin

router = Router()


@router.callback_query(F.data == "menu_ref")
async def on_ref(cb: CallbackQuery) -> None:
	ref_link = f"https://t.me/{(await cb.bot.me()).username}?start=ref{cb.from_user.id}"
	text = (
		"Реферальная программа\n\n"
		"Получайте 1000 токенов за приглашённого пользователя и 10% с его покупок (будет позже).\n\n"
		f"Моя реферальная ссылка:\n{ref_link}"
	)
	await cb.answer()
	await safe_edit_text(cb.message, text, reply_markup=main_menu_kb(is_admin=is_admin(cb.from_user.id)))


