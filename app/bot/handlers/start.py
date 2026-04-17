from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select
from loguru import logger
import asyncio

from app.bot.keyboards.main import main_menu_kb
from app.bot.keyboards.help import help_menu_kb
from .profile import router as profile_router
from .promo import router as promo_router
from .referral import router as referral_router
from .chat import router as chat_router
from .dialogs import router as dialogs_router
from .admin import router as admin_router
from .promo_admin import router as promo_admin_router
from app.bot.utils.tg import safe_edit_text
from app.bot.utils.auth import is_admin
from app.bot.utils.notifications import notify_admins_new_user
from app.db.session import async_session_maker
from app.db.models import User, Referral
from app.services.billing import reward_referral, ensure_balance

router = Router()
router.include_routers(profile_router)
router.include_routers(promo_router)
router.include_routers(referral_router)
router.include_routers(chat_router)
router.include_routers(dialogs_router)
router.include_routers(admin_router)
router.include_routers(promo_admin_router)


async def _delete_kb_message(bot, chat_id: int, message_id: int) -> None:
	"""Удаляет сообщение с клавиатурой через небольшую задержку"""
	await asyncio.sleep(0.2)
	try:
		await bot.delete_message(chat_id, message_id)
	except Exception:
		pass


async def get_main_menu_text(user_tg_id: int) -> str:
	"""Формирует текст афиши для главного меню с балансом токенов."""
	async with async_session_maker() as session:
		user_result = await session.execute(select(User).where(User.tg_id == user_tg_id))
		user = user_result.scalar_one_or_none()
		if not user:
			balance_tokens = 0
		else:
			balance = await ensure_balance(session, user_tg_id)
			balance_tokens = balance.tokens or 0
			await session.commit()
	
	formatted_tokens = f"{balance_tokens:,}".replace(",", " ")
	
	text = (
		"👋🏻 Привет! У тебя на балансе {tokens} токенов – используй их для запросов к нейросетям.\n\n"
		"💬 Языковые модели:\n"
		"– ChatGPT: работает с текстом, голосом, может принимать до 10 картинок или текстовый файл для анализа в одном запросе;\n"
		"– В разделе «💬 Диалоги» можешь создать чат со своей ролью, например: личный репетитор по английскому.\n\n"
		"🌄 Нейронки для создания фото:\n"
		"Замена лиц (дипфейк).\n\n"
		"✂️ Инструменты для работы с фото:\n"
		"– Улучшение качества, смена фона, удаление фона и векторизация.\n\n"
		"🎙 Инструменты для работы с аудио:\n"
		"– Расшифровка аудио в текст и преобразование текста в речь.\n\n"
		"По всем вопросам писать – @twix_gw\n"
		"Наш канал по промтам – @EnNeuroGPT"
	).format(tokens=formatted_tokens)
	
	return text


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
	# Обработка реферальной ссылки: /start ref<tg_id>
	if message.text and " " in message.text:
		arg = message.text.split(" ", 1)[1].strip()
		if arg.startswith("ref"):
			try:
				referrer_tg_id = int(arg[3:])
				invited_tg_id = message.from_user.id
				
				logger.info(f"Реферальная ссылка: referrer={referrer_tg_id}, invited={invited_tg_id}")
				
				# Не начисляем самому себе
				if referrer_tg_id == invited_tg_id:
					logger.info("Попытка самоприглашения, игнорируем")
					await message.answer(
						"Добро пожаловать! Выберите раздел:",
						reply_markup=main_menu_kb(is_admin=is_admin(message.from_user.id)),
					)
					return
				
				async with async_session_maker() as session:
					# Создаём реферера если нет
					referrer_result = await session.execute(select(User).where(User.tg_id == referrer_tg_id))
					referrer = referrer_result.scalar_one_or_none()
					if not referrer:
						logger.info(f"Создаём реферера {referrer_tg_id}")
						referrer = User(
							tg_id=referrer_tg_id,
							username=None,
							ref_code=f"ref{referrer_tg_id}",
						)
						session.add(referrer)
						await session.flush()
					
					# Убеждаемся, что у реферера есть баланс
					await ensure_balance(session, referrer.tg_id)
					
					# Создаём приглашённого пользователя если нет
					user_result = await session.execute(select(User).where(User.tg_id == invited_tg_id))
					user = user_result.scalar_one_or_none()
					if not user:
						logger.info(f"Создаём приглашённого пользователя {invited_tg_id}")
						user = User(
							tg_id=invited_tg_id,
							username=message.from_user.username or None,
							ref_code=f"ref{invited_tg_id}",
						)
						session.add(user)
						await session.flush()
						# Отправляем уведомление администраторам о новом пользователе в фоне
						logger.info(f"Обнаружен новый пользователь в start: tg_id={user.tg_id}, создаем задачу уведомления")
						asyncio.create_task(notify_admins_new_user(message.bot, user, message.from_user.full_name))
					
					# Начисляем бонус рефереру (функция сама проверит, не начисляли ли уже)
					logger.info(f"Попытка начисления бонуса рефереру {referrer_tg_id} за {invited_tg_id}")
					logger.info(f"Реферер: id={referrer.id}, tg_id={referrer.tg_id}")
					logger.info(f"Приглашённый: id={user.id}, tg_id={user.tg_id}")
					
					rewarded, status = await reward_referral(session, referrer_tg_id=referrer.tg_id, invited_user_tg_id=user.tg_id, reward=1000)
					await session.commit()
					
					logger.info(f"Результат начисления: rewarded={rewarded}, status={status}")
					
					# Отправляем уведомление рефереру в зависимости от статуса
					try:
						if status == "success":
							# Бонус успешно начислен
							logger.info(f"Отправка уведомления рефереру {referrer_tg_id} о начислении бонуса")
							await message.bot.send_message(
								referrer_tg_id,
								f"🎉 Вам начислено 1 000 токенов!\n\n"
								f"Ваш друг зарегистрировался по вашей реферальной ссылке.\n"
								f"ID приглашённого: <code>{invited_tg_id}</code>",
								parse_mode="HTML"
							)
							logger.info("Уведомление о начислении отправлено успешно")
						elif status == "already_rewarded":
							# Бонус уже был начислен ранее
							logger.info(f"Отправка уведомления рефереру {referrer_tg_id} о повторном переходе")
							await message.bot.send_message(
								referrer_tg_id,
								f"ℹ️ Пользователь перешёл по вашей реферальной ссылке.\n\n"
								f"ID пользователя: <code>{invited_tg_id}</code>\n"
								f"Бонус был начислен ранее за данного пользователя.",
								parse_mode="HTML"
							)
							logger.info("Уведомление о повторном переходе отправлено успешно")
						elif status == "error":
							# Ошибка (пользователь не найден) - не отправляем уведомление
							logger.warning(f"Ошибка при начислении бонуса: status={status} для реферера {referrer_tg_id} и приглашённого {invited_tg_id}")
					except Exception as e:
						logger.error(f"Ошибка отправки уведомления рефереру: {e}")
			
			except ValueError as e:
				logger.error(f"Ошибка парсинга реферальной ссылки: {e}")
			except Exception as e:
				logger.error(f"Ошибка обработки реферальной ссылки: {e}", exc_info=True)
	
	# Обычное приветствие
	# Проверяем и создаем пользователя если его нет
	async with async_session_maker() as session:
		user_result = await session.execute(select(User).where(User.tg_id == message.from_user.id))
		user = user_result.scalar_one_or_none()
		if not user:
			logger.info(f"Создаём нового пользователя при обычном /start: tg_id={message.from_user.id}")
			user = User(
				tg_id=message.from_user.id,
				username=message.from_user.username or None,
				ref_code=f"ref{message.from_user.id}",
			)
			session.add(user)
			await session.flush()
			await session.commit()
			# Отправляем уведомление администраторам о новом пользователе в фоне
			logger.info(f"Обнаружен новый пользователь в start (обычный): tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(message.bot, user, message.from_user.full_name))
		else:
			logger.debug(f"Пользователь {message.from_user.id} уже существует в БД (user_id={user.id}), уведомление не отправляется")
			await session.commit()
	
	# Убираем Reply Keyboard если она была показана
	from aiogram.types import ReplyKeyboardRemove, FSInputFile
	from app.bot.handlers.chat import ChatStates
	from app.bot.handlers.dialogs import DialogStates
	
	# Проверяем состояние и удаляем служебные сообщения
	current_state = await state.get_state()
	if current_state == ChatStates.wait_message or current_state == DialogStates.wait_message:
		data = await state.get_data()
		kb_message_id = data.get("kb_message_id")
		if kb_message_id:
			try:
				await message.bot.delete_message(message.chat.id, kb_message_id)
			except Exception:
				pass
		await state.clear()
	
	# Отправляем главное меню с афишей и фото
	# Инициализируем _admin_flag перед использованием
	_admin_flag = is_admin(message.from_user.id)
	text = await get_main_menu_text(message.from_user.id)
	photo_path = "photo_2025-12-03_02-41-09.jpg"
	
	# Проверяем наличие файла фото
	import os
	photo_exists = os.path.exists(photo_path)
	
	# Показываем ReplyKeyboard с кнопкой "В главное меню"
	from app.bot.keyboards.main import main_menu_reply_kb
	
	# Отправляем афишу с фото и ReplyKeyboard вместе
	# InlineKeyboard отправляем отдельным сообщением
	from app.bot.keyboards.main import main_menu_reply_kb
	
	if photo_exists:
		try:
			photo = FSInputFile(photo_path)
			# Отправляем фото с текстом и ReplyKeyboard
			await message.answer_photo(photo, caption=text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
		except Exception as e:
			logger.error(f"Ошибка отправки фото: {e}")
			await message.answer(text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
	else:
		# Если фото нет, просто отправляем текст
		logger.warning(f"Файл фото не найден: {photo_path}")
		await message.answer(text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
	
	# Отправляем InlineKeyboard отдельным сообщением
	# Добавляем очень много пробелов для расширения до границы экрана
	menu_text = "Выберите раздел:" + " " * 300
	await message.answer(menu_text, reply_markup=main_menu_kb(is_admin=_admin_flag))


@router.callback_query(F.data == "menu_main")
async def menu_main(cb: CallbackQuery, state: FSMContext) -> None:
	# Отвечаем на callback сразу, чтобы кнопка работала
	await cb.answer()
	
	# Проверяем, находимся ли мы в состоянии чата или диалога
	from app.bot.handlers.chat import ChatStates
	from app.bot.handlers.dialogs import DialogStates
	from aiogram.types import ReplyKeyboardRemove
	
	current_state = await state.get_state()
	if current_state == ChatStates.wait_message or current_state == DialogStates.wait_message:
		# Если мы в чате или диалоге, убираем Reply Keyboard и очищаем состояние
		data = await state.get_data()
		kb_message_id = data.get("kb_message_id")
		
		# Удаляем служебное сообщение с клавиатурой
		if kb_message_id:
			try:
				await cb.bot.delete_message(cb.message.chat.id, kb_message_id)
			except Exception:
				pass
		
		await state.clear()
	
	# Показываем главное меню С фото (как в cmd_start)
	# В главном меню показываем афишу с фото и ReplyKeyboard вместе
	from app.bot.keyboards.main import main_menu_reply_kb
	from aiogram.types import FSInputFile
	import os
	
	admin_flag = is_admin(cb.from_user.id)
	text = await get_main_menu_text(cb.from_user.id)
	photo_path = "photo_2025-12-03_02-41-09.jpg"
	photo_exists = os.path.exists(photo_path)
	
	# Удаляем старое сообщение если есть
	if cb.message.photo or cb.message.text:
		try:
			await cb.message.delete()
		except Exception:
			pass
	
	# Отправляем афишу с фото и ReplyKeyboard
	if photo_exists:
		try:
			photo = FSInputFile(photo_path)
			await cb.bot.send_photo(
				cb.message.chat.id,
				photo,
				caption=text,
				reply_markup=main_menu_reply_kb(),
				parse_mode="HTML"
			)
		except Exception as e:
			logger.error(f"Ошибка отправки фото: {e}")
			await cb.bot.send_message(
				cb.message.chat.id,
				text,
				reply_markup=main_menu_reply_kb(),
				parse_mode="HTML"
			)
	else:
		logger.warning(f"Файл фото не найден: {photo_path}")
		await cb.bot.send_message(
			cb.message.chat.id,
			text,
			reply_markup=main_menu_reply_kb(),
			parse_mode="HTML"
		)
	
	# Отправляем InlineKeyboard отдельным сообщением
	# Добавляем очень много пробелов для расширения до границы экрана
	menu_text = "Выберите раздел:" + " " * 300
	await cb.bot.send_message(
		cb.message.chat.id,
		menu_text,
		reply_markup=main_menu_kb(is_admin=admin_flag)
		)


@router.callback_query(F.data == "menu_help")
async def on_help(cb: CallbackQuery) -> None:
	await cb.answer()
	await safe_edit_text(cb.message, "❓ Выберите интересующий раздел", reply_markup=help_menu_kb())


# Аккордеон-меню помощи
@router.callback_query(F.data.startswith("help_expand:"))
async def help_expand(cb: CallbackQuery) -> None:
	await cb.answer()
	section = cb.data.split(":", 1)[1]
	
	texts = {
		"tokens": (
			"💎 Токены\n\n"
			"Что такое токен?\n"
			"Токен — это валюта нашего бота. С помощью неё вы можете общаться с GPT‑5, анализировать изображения и работать с аудио.\n\n"
			"Как тратятся токены в GPT‑5?\n"
			"• 1 токен ≈ 1 символ на русском\n"
			"• 1 токен ≈ 4 символам на английском\n\n"
			"У меня не осталось токенов, что делать?\n"
			"• Вы можете купить подписку в разделе «💎 Подписка»\n"
			"• Вы можете активировать промокод в разделе «🎟 Активировать промокод»\n"
			"• Пригласите друга и получите +1 000 токенов\n\n"
			"❗ Во всех разделах бот уведомляет вас о том, сколько токенов было затрачено и/или будет затрачено и сколько токенов осталось."
		),
		"payments": (
			"💳 Платежи\n\n"
			"Все наши тарифы представлены в разделе «💎 Подписка».\n\n"
			"Токены зачисляются на ваш баланс автоматически в течение 5 минут после оплаты.\n\n"
			"В случае если вы оплатили, но токены не зачислились в течение 5 минут, напишите администратору по кнопке ниже.\n\n"
			"Статусы платежей:\n"
			"🟡 Новый — новый, ожидает проверки\n"
			"🟡 Ожидает — ожидает платёж и проверяет оплату\n"
			"🟢 Завершён — платёж завершён\n"
			"🔴 Отменён — платёж отклонён или истекло время ожидания.\n\n"
			"Типы платежей:\n"
			"1. Оплата — оплата тарифа или услуги\n"
			"2. Промокод — был активирован промокод\n"
			"3. Реферальная программа — начисление токенов за нового реферала\n"
			"4. Обнуление баланса — происходит в случае мошенничества или блокировки аккаунта за неоднократное нарушение правил сервиса."
		),
		"chat": (
			"💬 ChatGPT. Ответы на часто задаваемые вопросы.\n\n"
			"У меня было 50 токенов на балансе, но мой запрос всё равно обработался и забрал больше, почему?\n"
			"Не волнуйтесь, это нормально. Мы даём право на последний бесплатный запрос. Это значит, что если запрос к чату затратил больше токенов, чем у вас есть, то бот спишет только те, что у вас остались и не будет уводить ваш баланс токенов в минус.\n\n"
			"Почему чат сохраняет не всю историю, а только последние несколько сообщений?\n"
			"Система хранит только последние 6 сообщений в чате. Это сделано для экономии токенов и избежания ошибок со стороны OpenAI. _Помните, диалог с сохранением истории тратит намного больше токенов, чем без сохранения._"
		),
		"support": (
			"📬 Реклама и сотрудничество\n\n"
			"По рекламе/сотрудничеству и предложениям по улучшению бота пишите по контактам ниже."
		),
		"policy": (
			"📚 Политика хранения данных\n\n"
			"Мы трепетно относимся к данным наших пользователей и поэтому решили написать эту политику, чтобы вы были уведомлены, как мы храним данные.\n\n"
			"Администрация бота имеет доступ только к управлению вашим аккаунтом (блокировка, выдача определённых прав и иные сервисные функции), но прав на доступ к истории ваших запросов у неё нет.\n\n"
			"Ниже приведён перечень данных, которые мы временно храним на своих серверах.\n\n"
			"GPT‑5:\n"
			"1. История ваших запросов в диалоге хранится на сервере до момента, пока вы не выполните очистку диалога по команде «/clear» или «Очистить историю».\n"
			"2. История ваших запросов через команду «/gpt _вопрос_» хранится до конца суток и автоматически очищается системой.\n\n"
			"❗ Система очищает только вопрос-ответ и хранит информацию о потраченных токенах за запрос для извлечения статистики по тратам."
		),
	}
	
	text = texts.get(section, "❓ Выберите интересующий раздел")
	await safe_edit_text(cb.message, text, reply_markup=help_menu_kb(expanded=section))


@router.callback_query(F.data.startswith("help_collapse:"))
async def help_collapse(cb: CallbackQuery) -> None:
	await cb.answer()
	await safe_edit_text(cb.message, "❓ Выберите интересующий раздел", reply_markup=help_menu_kb())


# Обработчики команд бота
@router.message(Command("buy"))
async def cmd_buy(message: Message, state: FSMContext) -> None:
	"""Команда /buy - перенаправляет в меню подписки."""
	from app.bot.keyboards.subscribe import subscribe_menu_kb
	from app.bot.keyboards.main import main_menu_reply_kb
	await state.clear()
	await message.answer("💎 Оформить подписку. Выберите тариф:", reply_markup=subscribe_menu_kb())
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.message(Command("myprofile"))
async def cmd_myprofile(message: Message, state: FSMContext) -> None:
	"""Команда /myprofile - перенаправляет в меню профиля."""
	from app.bot.handlers.profile import _ensure_user, _format_tokens
	from app.bot.keyboards.profile import profile_menu_kb
	from app.services.billing import ensure_balance
	from sqlalchemy import select, func
	from datetime import datetime, timezone
	from app.db.models import Usage
	import asyncio
	
	await state.clear()
	
	async with async_session_maker() as session:
		# Создаём фиктивный CallbackQuery для _ensure_user
		class FakeCallbackQuery:
			def __init__(self, from_user):
				self.from_user = from_user
		
		fake_cb = FakeCallbackQuery(message.from_user)
		user, is_new = await _ensure_user(session, fake_cb)
		# Отправляем уведомление администраторам в фоне, если пользователь новый
		if is_new:
			logger.info(f"Обнаружен новый пользователь в myprofile: tg_id={user.tg_id}, создаем задачу уведомления")
			asyncio.create_task(notify_admins_new_user(message.bot, user, message.from_user.full_name))
		
		balance = await ensure_balance(session, user.tg_id)
		
		# Подсчитываем статистику использования токенов
		usage_stats = await session.execute(
			select(Usage.model, func.sum(Usage.tokens_used).label("total"))
			.where(Usage.user_id == user.id)
			.group_by(Usage.model)
		)
		stats_dict = {row.model: row.total for row in usage_stats.all()}
		total_spent = sum(stats_dict.values())
		
		await session.commit()

	tokens = balance.tokens or 0
	
	# Проверяем подписку и вычисляем дни до окончания
	subscription_info = ""
	if balance.expires_at:
		now = datetime.now(timezone.utc)
		expires_at_utc = balance.expires_at.replace(tzinfo=timezone.utc) if balance.expires_at.tzinfo is None else balance.expires_at
		
		if expires_at_utc > now:
			delta = expires_at_utc - now
			days_left = delta.days
			if days_left >= 0:
				subscription_info = f"\nДо завершения подписки осталось: {days_left} дней"
	
	# Формируем статистику
	stats_lines = []
	if total_spent > 0:
		# ChatGPT (все режимы с gpt в названии модели)
		chatgpt_total = sum(v for k, v in stats_dict.items() if "gpt" in k.lower() or "chatgpt" in k.lower())
		if chatgpt_total > 0:
			stats_lines.append(f"- ChatGPT: {_format_tokens(chatgpt_total)}")
		
		# Другие модели (если есть)
		for model, amount in stats_dict.items():
			if "gpt" not in model.lower() and "chatgpt" not in model.lower():
				model_name = model.replace("_", " ").title()
				stats_lines.append(f"- {model_name}: {_format_tokens(amount)}")
	
	if not stats_lines:
		stats_lines.append("- ChatGPT: 0")
	
	stats_text = "\n".join(stats_lines)
	
	user_id = str(message.from_user.id)
	text = (
		"👤 Мой профиль\n\n"
		f"ID: <code>{user_id}</code>\n"
		f"Имя: {message.from_user.full_name}\n"
		f"Баланс: {_format_tokens(tokens)} токенов{subscription_info}\n\n"
		"На какие сервисы хватит баланса? · примерно:\n"
		"• 2 000 запросов к GPT‑5 (текст)\n"
		"• 400 запросов с анализом фото\n"
		"• 333 минуты расшифровки аудио\n"
		"• 100 000 символов перевода текста в голос\n\n"
		f"🔸 Потрачено: {_format_tokens(total_spent)} токенов\n"
		f"{stats_text}\n\n"
		"ℹ️ Расход зависит от длины запросов и выбранного режима."
	)
	await message.answer(text, reply_markup=profile_menu_kb())


@router.message(Command("instructions"))
async def cmd_instructions(message: Message, state: FSMContext) -> None:
	"""Команда /instructions - перенаправляет в меню помощи."""
	from app.bot.keyboards.main import main_menu_reply_kb
	await state.clear()
	await message.answer("❓ Выберите интересующий раздел", reply_markup=help_menu_kb())
	# ReplyKeyboard показывается только в главном меню, здесь используем только inline кнопки


@router.message(Command("refsystem"))
async def cmd_refsystem(message: Message, state: FSMContext) -> None:
	"""Команда /refsystem - перенаправляет в меню реферальной программы."""
	from app.bot.keyboards.profile import referral_kb
	
	await state.clear()
	
	bot_me = await message.bot.me()
	ref_link = f"https://t.me/{bot_me.username}?start=ref{message.from_user.id}"
	text = (
		"👥 Реферальная программа\n\n"
		"Получайте 1 000 токенов за каждого приглашённого пользователя.\n\n"
		"🔗 Моя реферальная ссылка:\n"
		f"<code>{ref_link}</code>\n\n"
		"1. Поделитесь ссылкой ниже\n"
		"2. Друг запускает бота и авторизуется\n"
		"3. После активации ему начисляются токены, а вам — бонус 1 000 токенов\n\n"
		"💡 Начисление происходит автоматически сразу после регистрации приглашённого."
	)
	await message.answer(text, reply_markup=referral_kb(ref_link))


@router.message(F.text == "← В главное меню")
async def handle_main_menu_reply(message: Message, state: FSMContext) -> None:
	"""Обработчик ReplyKeyboard кнопки возврата в главное меню."""
	from app.bot.handlers.chat import ChatStates
	from app.bot.handlers.dialogs import DialogStates
	
	# Очищаем состояние если есть
	current_state = await state.get_state()
	if current_state == ChatStates.wait_message or current_state == DialogStates.wait_message:
		data = await state.get_data()
		kb_message_id = data.get("kb_message_id")
		if kb_message_id:
			try:
				await message.bot.delete_message(message.chat.id, kb_message_id)
			except Exception:
				pass
	
	await state.clear()
	
	# Отправляем главное меню С фото (как в cmd_start)
	# Показываем афишу с фото и ReplyKeyboard вместе
	from app.bot.keyboards.main import main_menu_reply_kb
	from aiogram.types import FSInputFile
	import os
	
	admin_flag = is_admin(message.from_user.id)
	text = await get_main_menu_text(message.from_user.id)
	photo_path = "photo_2025-12-03_02-41-09.jpg"
	photo_exists = os.path.exists(photo_path)
	
	if photo_exists:
		try:
			photo = FSInputFile(photo_path)
			await message.answer_photo(photo, caption=text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
		except Exception as e:
			logger.error(f"Ошибка отправки фото: {e}")
			await message.answer(text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
	else:
		logger.warning(f"Файл фото не найден: {photo_path}")
		await message.answer(text, reply_markup=main_menu_reply_kb(), parse_mode="HTML")
	
	# Отправляем InlineKeyboard отдельным сообщением
	# Добавляем очень много пробелов для расширения до границы экрана
	menu_text = "Выберите раздел:" + " " * 300
	await message.answer(menu_text, reply_markup=main_menu_kb(is_admin=admin_flag))


