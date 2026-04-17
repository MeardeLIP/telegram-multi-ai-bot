"""
Утилиты для отправки уведомлений администраторам и пользователям.
"""
from aiogram import Bot
from loguru import logger
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User, Balance, SubscriptionNotification
from app.db.session import async_session_maker


async def notify_admins_new_user(bot: Bot, user: User, user_name: str) -> None:
	"""
	Отправляет уведомление всем администраторам о регистрации нового пользователя.
	
	Args:
		bot: Экземпляр бота для отправки сообщений
		user: Объект пользователя из БД
		user_name: Имя пользователя (full_name из Telegram)
	"""
	logger.info(f"Попытка отправить уведомление о новом пользователе: tg_id={user.tg_id}, name={user_name}")
	
	settings = get_settings()
	admin_ids = settings.admin_ids
	
	logger.info(f"Список администраторов из настроек: {admin_ids}")
	
	if not admin_ids:
		logger.warning("Список администраторов пуст! Проверьте переменную ADMIN_IDS в .env файле")
		return
	
	# Формируем имя пользователя для отображения
	display_name = user_name or "Не указано"
	
	# Формируем строку с именем пользователя и кликабельной ссылкой (если есть username)
	if user.username:
		user_info = f'<a href="https://t.me/{user.username}">{display_name}</a>'
	else:
		user_info = display_name
	
	# Извлекаем ID из реферального кода (убираем префикс "ref" если есть)
	ref_code_display = user.ref_code or str(user.tg_id)
	if ref_code_display.startswith("ref"):
		ref_code_display = ref_code_display[3:]  # Убираем "ref" префикс
	
	# Формируем сообщение согласно референсу
	message_text = (
		f"✨ У Вас новый пользователь! ✨\n\n"
		f"👤 Пользователь: {user_info}\n\n"
		f"🆔 Telegram ID: <code>{user.tg_id}</code>\n"
		f"🏷 Реферальный код: <code>{ref_code_display}</code>"
	)
	
	logger.info(f"Отправка уведомлений {len(admin_ids)} администраторам о пользователе {user.tg_id}")
	
	# Отправляем уведомление каждому администратору
	for admin_id in admin_ids:
		try:
			logger.info(f"Отправка уведомления администратору {admin_id}...")
			await bot.send_message(
				admin_id,
				message_text,
				parse_mode="HTML"
			)
			logger.info(f"✅ Уведомление о новом пользователе {user.tg_id} успешно отправлено администратору {admin_id}")
		except Exception as e:
			# Игнорируем ошибки (админ мог заблокировать бота и т.д.)
			logger.error(f"❌ Не удалось отправить уведомление администратору {admin_id}: {type(e).__name__}: {e}")


async def check_subscription_expiry(bot: Bot) -> None:
	"""
	Проверяет подписки пользователей и отправляет уведомления о скором окончании.
	Отправляет уведомления за 7 дней и за 3 дня до окончания подписки.
	"""
	logger.info("Начинаю проверку подписок на предмет окончания...")
	
	async with async_session_maker() as session:
		# Получаем всех пользователей с активными подписками
		now = datetime.now(timezone.utc)
		
		result = await session.execute(
			select(Balance, User)
			.join(User, Balance.user_id == User.id)
			.where(Balance.expires_at.isnot(None))
			.where(Balance.expires_at > now)
		)
		balances_with_users = result.all()
		
		logger.info(f"Найдено {len(balances_with_users)} пользователей с активными подписками")
		
		notifications_sent = 0
		
		for balance, user in balances_with_users:
			expires_at_utc = balance.expires_at.replace(tzinfo=timezone.utc) if balance.expires_at.tzinfo is None else balance.expires_at
			delta = expires_at_utc - now
			days_left = delta.days
			
			# Проверяем, нужно ли отправить уведомление за 7 дней
			if days_left == 7:
				notification_type = "7_days"
				# Проверяем, не отправляли ли уже это уведомление
				existing = await session.execute(
					select(SubscriptionNotification)
					.where(SubscriptionNotification.user_id == user.id)
					.where(SubscriptionNotification.notification_type == notification_type)
				)
				if existing.scalar_one_or_none() is None:
					# Отправляем уведомление
					message_text = (
						"⏰ Напоминание о подписке\n\n"
						"До окончания вашей подписки осталось 7 дней.\n\n"
						"Не забудьте продлить подписку, чтобы продолжить пользоваться всеми возможностями бота!"
					)
					try:
						await bot.send_message(
							chat_id=user.tg_id,
							text=message_text,
							parse_mode="HTML",
						)
						# Сохраняем информацию об отправленном уведомлении
						notification = SubscriptionNotification(
							user_id=user.id,
							notification_type=notification_type,
						)
						session.add(notification)
						await session.commit()
						notifications_sent += 1
						logger.info(f"Отправлено уведомление за 7 дней пользователю {user.tg_id}")
					except Exception as e:
						logger.error(f"Ошибка при отправке уведомления пользователю {user.tg_id}: {e}")
						await session.rollback()
			
			# Проверяем, нужно ли отправить уведомление за 3 дня
			elif days_left == 3:
				notification_type = "3_days"
				# Проверяем, не отправляли ли уже это уведомление
				existing = await session.execute(
					select(SubscriptionNotification)
					.where(SubscriptionNotification.user_id == user.id)
					.where(SubscriptionNotification.notification_type == notification_type)
				)
				if existing.scalar_one_or_none() is None:
					# Отправляем уведомление
					message_text = (
						"⏰ Напоминание о подписке\n\n"
						"До окончания вашей подписки осталось 3 дня.\n\n"
						"Не забудьте продлить подписку, чтобы продолжить пользоваться всеми возможностями бота!"
					)
					try:
						await bot.send_message(
							chat_id=user.tg_id,
							text=message_text,
							parse_mode="HTML",
						)
						# Сохраняем информацию об отправленном уведомлении
						notification = SubscriptionNotification(
							user_id=user.id,
							notification_type=notification_type,
						)
						session.add(notification)
						await session.commit()
						notifications_sent += 1
						logger.info(f"Отправлено уведомление за 3 дня пользователю {user.tg_id}")
					except Exception as e:
						logger.error(f"Ошибка при отправке уведомления пользователю {user.tg_id}: {e}")
						await session.rollback()
		
		logger.info(f"Проверка подписок завершена. Отправлено уведомлений: {notifications_sent}")

