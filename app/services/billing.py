from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import select, update, func, Integer as SAInteger, case
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.config import get_settings
from app.db.models import Balance, Payment, User
from app.db.models import PromoCode, PromoCodeUsage, Referral, Usage


PlanCode = Literal["P1D_50K", "P7D_125K", "P7D_300K", "P30D_1M", "P30D_5M"]


PLANS: dict[PlanCode, tuple[int, timedelta]] = {
	"P1D_50K": (50_000, timedelta(days=1)),
	"P7D_125K": (125_000, timedelta(days=7)),
	"P7D_300K": (300_000, timedelta(days=7)),
	"P30D_1M": (1_000_000, timedelta(days=30)),
	"P30D_5M": (5_000_000, timedelta(days=30)),
}


async def ensure_balance(session: AsyncSession, tg_id: int) -> Balance:
	"""
	Обеспечивает наличие баланса для пользователя.
	Принимает tg_id (Telegram ID), находит или создает пользователя и баланс.
	"""
	# Ищем пользователя по tg_id
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	
	if not user:
		# Если пользователя нет, создаем его
		logger.info(f"ensure_balance: создаём пользователя tg_id={tg_id}")
		user = User(tg_id=tg_id, username=None, ref_code=f"ref{tg_id}")
		session.add(user)
		await session.flush()
		logger.info(f"ensure_balance: пользователь создан, id={user.id}")
	else:
		logger.info(f"ensure_balance: пользователь найден, id={user.id}, tg_id={user.tg_id}")
	
	# Теперь ищем баланс по user.id (внутренний ID)
	result = await session.execute(select(Balance).where(Balance.user_id == user.id))
	bal = result.scalar_one_or_none()
	if bal:
		logger.info(f"ensure_balance: баланс найден, user_id={user.id}, tokens={bal.tokens}")
		return bal
	
	# Создаем баланс
	logger.info(f"ensure_balance: создаём баланс для user_id={user.id}")
	bal = Balance(user_id=user.id, tokens=0, subscription_tier=None, expires_at=None, auto_renew=False)
	session.add(bal)
	await session.flush()
	logger.info(f"ensure_balance: баланс создан, user_id={user.id}, tokens={bal.tokens}")
	return bal


async def apply_plan_payment(session: AsyncSession, tg_id: int, plan: PlanCode) -> Balance:
	"""
	Применяет оплату плана для пользователя.
	Принимает tg_id (Telegram ID).
	"""
	tokens, period = PLANS[plan]

	bal = await ensure_balance(session, tg_id)

	now = datetime.utcnow()
	new_expires = now + period if not bal.expires_at or bal.expires_at < now else bal.expires_at + period

	bal.tokens = (bal.tokens or 0) + tokens
	bal.subscription_tier = plan
	bal.expires_at = new_expires

	await session.flush()
	return bal


def estimate_text_tokens_rus(chars: int) -> int:
	# 1 токен ~ 1 символ на русском
	return chars


async def check_balance(session: AsyncSession, tg_id: int, amount: int) -> bool:
	"""
	Проверяет достаточность баланса для списания токенов.
	Принимает tg_id (Telegram ID) и количество токенов.
	Возвращает True если баланса достаточно, False если недостаточно.
	"""
	bal = await ensure_balance(session, tg_id)
	available = bal.tokens or 0
	sufficient = available >= amount
	logger.info(
		f"check_balance: tg_id={tg_id}, требуется={amount}, доступно={available}, достаточно={sufficient}"
	)
	return sufficient


async def debit_tokens(
	session: AsyncSession,
	tg_id: int,
	amount: int,
	model: str = "gpt-5",
	mode: str = "text",
	success: bool = True,
	error_message: str | None = None
) -> tuple[Balance, bool]:
	"""
	Списывает токены с баланса пользователя.
	Принимает tg_id (Telegram ID).
	Возвращает кортеж (Balance, success), где success = True если списание успешно, False если баланса недостаточно.
	"""
	bal = await ensure_balance(session, tg_id)
	current_balance = bal.tokens or 0
	
	if current_balance < amount:
		# Баланса недостаточно, не списываем
		logger.warning(f"Недостаточно токенов: требуется {amount}, доступно {current_balance} для пользователя {tg_id}")
		return bal, False
	
	# Списываем токены
	bal.tokens = current_balance - amount
	
	# Записываем использование токенов в статистику (только фактически списанную сумму)
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	if user:
		usage = Usage(
			user_id=user.id,
			tokens_used=amount,
			model=model,
			mode=mode,
			success=success,
			error_message=error_message
		)
		session.add(usage)
	
	await session.flush()
	return bal, True


async def apply_promocode(session: AsyncSession, tg_id: int, code: str) -> int:
	"""
	Применяет промокод для пользователя.
	Принимает tg_id (Telegram ID).
	Возвращает количество начисленных токенов (0 если промокод недействителен или уже использован).
	"""
	# Приводим код к верхнему регистру для поиска
	code_upper = code.upper().strip()
	pc = await session.get(PromoCode, code_upper)
	
	if not pc:
		return 0
	
	if not pc.active:
		return 0
	
	# Проверяем срок действия
	if pc.expires_at:
		expires_at_utc = pc.expires_at.replace(tzinfo=timezone.utc) if pc.expires_at.tzinfo is None else pc.expires_at
		if expires_at_utc < datetime.now(timezone.utc):
			return 0
	
	# Проверяем лимит использований
	if pc.used_count >= pc.max_uses:
		return 0
	
	# Находим пользователя по tg_id
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	if not user:
		return 0
	
	# Проверяем, использовал ли уже этот пользователь этот промокод
	usage_result = await session.execute(
		select(PromoCodeUsage).where(
			PromoCodeUsage.user_id == user.id,
			PromoCodeUsage.promo_code == code_upper
		)
	)
	existing_usage = usage_result.scalar_one_or_none()
	if existing_usage:
		logger.info(f"apply_promocode: промокод {code_upper} уже использован пользователем tg_id={tg_id}")
		return 0
	
	# Применяем промокод
	bal = await ensure_balance(session, tg_id)
	bal.tokens += pc.tokens_bonus
	pc.used_count += 1
	
	# Создаем запись об использовании промокода
	usage = PromoCodeUsage(user_id=user.id, promo_code=code_upper)
	session.add(usage)
	
	await session.flush()
	
	logger.info(f"apply_promocode: code={code_upper}, tg_id={tg_id}, tokens_bonus={pc.tokens_bonus}, discount={pc.discount_percent}%")
	return pc.tokens_bonus


async def grant_tokens(session: AsyncSession, tg_id: int, amount: int) -> Balance:
	"""
	Начисляет указанное количество токенов пользователю по его Telegram ID.
	Возвращает обновлённый баланс.
	"""
	if amount <= 0:
		raise ValueError("amount must be positive")

	bal = await ensure_balance(session, tg_id)
	bal.tokens = (bal.tokens or 0) + amount
	await session.flush()
	return bal


async def reward_referral(session: AsyncSession, referrer_tg_id: int, invited_user_tg_id: int, reward: int = 1000) -> tuple[bool, str]:
	"""
	Начисляет бонус рефереру за приглашённого пользователя.
	Принимает tg_id (Telegram ID) для обоих пользователей.
	Возвращает кортеж (success: bool, status: str):
	- (True, "success") - бонус успешно начислен
	- (False, "already_rewarded") - бонус уже был начислен ранее
	- (False, "error") - произошла ошибка (пользователь не найден)
	"""
	logger.info(f"reward_referral: referrer_tg_id={referrer_tg_id}, invited_user_tg_id={invited_user_tg_id}, reward={reward}")
	
	# Находим пользователей по tg_id
	referrer_result = await session.execute(select(User).where(User.tg_id == referrer_tg_id))
	referrer = referrer_result.scalar_one_or_none()
	invited_result = await session.execute(select(User).where(User.tg_id == invited_user_tg_id))
	invited = invited_result.scalar_one_or_none()
	
	if not referrer:
		logger.error(f"Реферер не найден: referrer_tg_id={referrer_tg_id}")
		return (False, "error")
	
	if not invited:
		logger.error(f"Приглашённый пользователь не найден: invited_user_tg_id={invited_user_tg_id}")
		return (False, "error")
	
	logger.info(f"Найдены пользователи: referrer.id={referrer.id}, invited.id={invited.id}")
	
	# Проверяем, не начисляли ли уже
	existing_result = await session.execute(
		select(Referral).where(
			Referral.user_id == referrer.id,
			Referral.invited_user_id == invited.id
		)
	)
	existing_ref = existing_result.scalar_one_or_none()
	if existing_ref:
		logger.info(f"Бонус уже был начислен ранее: referral.id={existing_ref.id}, rewarded_at={existing_ref.rewarded_at}")
		return (False, "already_rewarded")  # Уже начисляли
	
	# Убеждаемся, что у реферера есть баланс
	logger.info(f"Проверяем/создаём баланс для реферера tg_id={referrer_tg_id}")
	bal = await ensure_balance(session, referrer_tg_id)
	
	# Получаем текущий баланс ДО обновления
	old_tokens = bal.tokens or 0
	logger.info(f"Текущий баланс реферера ДО начисления: {old_tokens} токенов")
	
	# Создаём запись Referral
	logger.info(f"Создаём запись Referral: user_id={referrer.id}, invited_user_id={invited.id}, reward={reward}")
	ref = Referral(user_id=referrer.id, invited_user_id=invited.id, reward_tokens=reward, rewarded_at=datetime.utcnow())
	session.add(ref)
	
	# Обновляем баланс реферера
	new_tokens = old_tokens + reward
	bal.tokens = new_tokens
	logger.info(f"Баланс реферера обновлён: было {old_tokens}, стало {new_tokens}")
	logger.info(f"Balance object: user_id={bal.user_id}, tokens={bal.tokens}")
	
	# Фиксируем изменения в базе данных
	await session.flush()
	logger.info(f"Изменения зафиксированы через flush()")
	
	# После flush можно получить ID реферальной записи
	await session.refresh(ref)
	if ref.id:
		logger.info(f"Реферальная запись создана: Referral.id={ref.id}")
	else:
		logger.warning(f"Реферальная запись еще не имеет ID")
	
	return (True, "success")


async def get_user_balance(session: AsyncSession, tg_id: int) -> dict | None:
	"""
	Получает информацию о балансе пользователя по Telegram ID.
	Возвращает словарь с информацией о пользователе и балансе, или None если пользователь не найден.
	"""
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	
	if not user:
		return None
	
	balance_result = await session.execute(select(Balance).where(Balance.user_id == user.id))
	balance = balance_result.scalar_one_or_none()
	
	if not balance:
		# Создаем баланс, если его нет
		balance = Balance(user_id=user.id, tokens=0, subscription_tier=None, expires_at=None, auto_renew=False)
		session.add(balance)
		await session.flush()
	
	return {
		"tg_id": user.tg_id,
		"user_id": user.id,
		"username": user.username,
		"tokens": balance.tokens or 0,
		"subscription_tier": balance.subscription_tier,
		"expires_at": balance.expires_at,
		"created_at": user.created_at,
	}


async def deduct_tokens(session: AsyncSession, tg_id: int, amount: int) -> tuple[Balance, bool]:
	"""
	Списывает токены у пользователя (аналог grant_tokens, но с вычитанием).
	Возвращает кортеж (Balance, success), где success = True если списание успешно.
	"""
	if amount <= 0:
		raise ValueError("amount must be positive")
	
	bal = await ensure_balance(session, tg_id)
	current_balance = bal.tokens or 0
	
	if current_balance < amount:
		logger.warning(f"Недостаточно токенов для списания: требуется {amount}, доступно {current_balance} для пользователя {tg_id}")
		return bal, False
	
	bal.tokens = current_balance - amount
	await session.flush()
	return bal, True


async def get_user_usage_stats(session: AsyncSession, tg_id: int) -> dict | None:
	"""
	Получает статистику использования токенов пользователем.
	Возвращает словарь с общей статистикой, или None если пользователь не найден.
	"""
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	
	if not user:
		return None
	
	# Получаем все записи Usage для пользователя
	usage_result = await session.execute(
		select(
			func.count(Usage.id).label("total_requests"),
			func.sum(case((Usage.success == True, 1), else_=0)).label("successful_requests"),
			func.sum(Usage.tokens_used).label("total_tokens")
		).where(Usage.user_id == user.id)
	)
	stats = usage_result.first()
	
	total_requests = stats.total_requests or 0
	successful_requests = int(stats.successful_requests or 0)
	failed_requests = total_requests - successful_requests
	total_tokens = stats.total_tokens or 0
	
	return {
		"tg_id": user.tg_id,
		"user_id": user.id,
		"total_requests": total_requests,
		"successful_requests": successful_requests,
		"failed_requests": failed_requests,
		"total_tokens": total_tokens,
	}


async def get_user_usage_history(session: AsyncSession, tg_id: int, limit: int = 50) -> list[Usage] | None:
	"""
	Получает историю запросов пользователя.
	Возвращает список записей Usage, отсортированных по дате создания (новые первыми), или None если пользователь не найден.
	"""
	user_result = await session.execute(select(User).where(User.tg_id == tg_id))
	user = user_result.scalar_one_or_none()
	
	if not user:
		return None
	
	# Получаем последние N запросов
	usage_result = await session.execute(
		select(Usage)
		.where(Usage.user_id == user.id)
		.order_by(Usage.created_at.desc())
		.limit(limit)
	)
	usage_list = usage_result.scalars().all()
	
	return list(usage_list)


def calculate_requests_for_plan(tokens: int) -> dict:
	"""
	Рассчитывает количество запросов для каждого типа операций на основе количества токенов.
	Использует только реализованные функции.
	"""
	settings = get_settings()
	
	# Стоимости операций
	# Для текстовых запросов: 1 токен = 1 символ (estimate_text_tokens_rus)
	# По референсу: 1 000 000 токенов = 2 000 запросов → 500 токенов на запрос
	chatgpt_text_cost = 500  # Средний запрос к ChatGPT 5 Mini
	
	# Для vision: по референсу 1 000 000 токенов = 400 запросов → 2 500 токенов на запрос
	# В реальном коде списывается billing_vision_surcharge (150) за фото + текст через estimate_text_tokens_rus
	# Для расчета используем среднее значение из референса
	chatgpt_vision_cost = 2500  # ChatGPT 5 Mini с фото (среднее значение из референса)
	gpt_image_cost = settings.billing_gpt_image_cost  # 9500
	faceswap_cost = settings.billing_faceswap_cost  # 7500
	photo_enhance_cost = settings.billing_photo_enhance_cost  # 4000
	photo_replace_bg_cost = settings.billing_photo_replace_bg_cost  # 11000
	photo_remove_bg_cost = settings.billing_photo_remove_bg_cost  # 7500
	tts_per_char = 10  # 1 символ = 10 токенов
	stt_per_min = settings.billing_stt_per_min  # 900
	
	# Расчет количества запросов
	chatgpt_text_requests = tokens // chatgpt_text_cost
	chatgpt_vision_requests = tokens // chatgpt_vision_cost
	gpt_image_requests = tokens // gpt_image_cost
	faceswap_requests = tokens // faceswap_cost
	photo_enhance_requests = tokens // photo_enhance_cost
	photo_replace_bg_requests = tokens // photo_replace_bg_cost
	photo_remove_bg_requests = tokens // photo_remove_bg_cost
	tts_chars = tokens // tts_per_char
	stt_minutes = tokens // stt_per_min
	
	return {
		"chatgpt_text": chatgpt_text_requests,
		"chatgpt_vision": chatgpt_vision_requests,
		"gpt_image": gpt_image_requests,
		"faceswap": faceswap_requests,
		"photo_enhance": photo_enhance_requests,
		"photo_replace_bg": photo_replace_bg_requests,
		"photo_remove_bg": photo_remove_bg_requests,
		"tts_chars": tts_chars,
		"stt_minutes": stt_minutes,
	}


