import asyncio
import sys
import traceback
from aiogram import Bot, Dispatcher
from aiogram.types import CallbackQuery
from aiogram.client.default import DefaultBotProperties
from loguru import logger

from app.config import get_settings
from .handlers.start import router as start_router
from .handlers.subscribe import router as subscribe_router
from .handlers.vision import router as vision_router
from .handlers.faceswap import router as faceswap_router
from .handlers.audio import router as audio_router
from .handlers.photo import router as photo_router
from .handlers.create_photo import router as create_photo_router


async def _subscription_checker_task(bot: Bot) -> None:
	"""
	Фоновая задача для проверки подписок и отправки уведомлений.
	Запускается каждые 6 часов.
	"""
	from app.bot.utils.notifications import check_subscription_expiry
	
	while True:
		try:
			await asyncio.sleep(6 * 60 * 60)  # 6 часов
			await check_subscription_expiry(bot)
		except Exception as e:
			logger.error(f"Ошибка в задаче проверки подписок: {e}")
			await asyncio.sleep(60)  # Ждем минуту перед повтором при ошибке


async def run_bot() -> None:
	settings = get_settings()
	bot = Bot(
		token=settings.bot_token,
		default=DefaultBotProperties(parse_mode="HTML")
	)
	dp = Dispatcher()
	
	# Middleware для логирования всех callback_query
	@dp.callback_query.middleware()
	async def callback_query_logging_middleware(handler, event: CallbackQuery, data: dict):
		"""Логирует все входящие callback_query для отладки."""
		logger.info(f"🔵 CALLBACK RECEIVED: data='{event.data}', user_id={event.from_user.id}, message_id={event.message.message_id if event.message else None}")
		try:
			result = await handler(event, data)
			logger.info(f"✅ CALLBACK HANDLED: data='{event.data}'")
			return result
		except Exception as e:
			logger.error(f"❌ CALLBACK ERROR: data='{event.data}', error={e}")
			logger.error(f"Traceback: {traceback.format_exc()}")
			# Отвечаем на callback даже при ошибке
			try:
				await event.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=False)
			except Exception:
				pass
			raise
	
	# Регистрируем роутеры ПЕРВЫМИ
	dp.include_router(start_router)
	dp.include_router(subscribe_router)
	dp.include_router(faceswap_router)  # Должен быть ПЕРЕД vision_router, чтобы перехватывать фото в режиме FaceSwap
	dp.include_router(photo_router)  # Должен быть ПЕРЕД vision_router, чтобы перехватывать фото в режиме работы с фото
	dp.include_router(create_photo_router)  # Должен быть ПЕРЕД vision_router, чтобы перехватывать фото в режиме создания фото
	dp.include_router(vision_router)
	dp.include_router(audio_router)
	
	# Регистрируем глобальный обработчик ошибок ПОСЛЕ регистрации роутеров
	# В aiogram 3 обработчик ошибок может принимать разные сигнатуры в зависимости от версии
	@dp.errors()
	async def error_handler(*args, **kwargs):
		"""Глобальный обработчик ошибок для всех типов обновлений."""
		try:
			# Определяем event и exception из аргументов
			event = None
			exception = None
			
			if len(args) >= 2:
				event, exception = args[0], args[1]
			elif len(args) == 1:
				exception = args[0]
			elif 'event' in kwargs:
				event = kwargs.get('event')
				exception = kwargs.get('exception') or kwargs.get('error')
			
			# Если exception не найден, пытаемся найти в kwargs
			if exception is None:
				exception = kwargs.get('exception') or kwargs.get('error')
			
			logger.error(f"🚨 ERROR HANDLER: exception={exception}, exception_type={type(exception) if exception else None}")
			if event:
				logger.error(f"🚨 ERROR HANDLER: event_type={type(event)}")
			logger.error(f"Traceback: {traceback.format_exc()}")
			
			# Если это callback_query, отвечаем на него
			if event and isinstance(event, CallbackQuery):
				logger.error(f"Callback data: {event.data}, User ID: {event.from_user.id}")
				try:
					await event.answer("❌ Произошла ошибка. Попробуйте позже.", show_alert=False)
				except Exception as e:
					logger.error(f"Не удалось ответить на callback: {e}")
		except Exception as e:
			logger.error(f"Критическая ошибка в обработчике ошибок: {e}")
			logger.error(f"Traceback: {traceback.format_exc()}")

	logger.info("Starting Telegram bot")
	
	# Запускаем фоновую задачу для проверки подписок
	asyncio.create_task(_subscription_checker_task(bot))
	logger.info("Background subscription checker task started")
	
	await dp.start_polling(bot)


if __name__ == "__main__":
	# Исправление для Windows: psycopg требует SelectorEventLoop, а не ProactorEventLoop
	if sys.platform == "win32":
		asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
	asyncio.run(run_bot())


