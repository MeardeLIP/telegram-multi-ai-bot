"""
Сервис для работы с KLING-V2 API - оживление фото (image to video).
"""
import httpx
import asyncio
import time
from typing import Literal
from loguru import logger
import jwt
from app.config import get_settings
from app.services.llm import vision_analyze, chat_completion

settings = get_settings()


def _map_mode_to_api(mode: str) -> str:
	"""
	Преобразует UI значения mode в значения, ожидаемые KLING API.
	
	Args:
		mode: Режим из UI ("standard" или "pro")
		
	Returns:
		str: Значение mode для API ("std" или "pro")
	"""
	mapping = {
		"standard": "std",
		"pro": "pro"
	}
	
	api_mode = mapping.get(mode, mode)
	if api_mode != mode:
		logger.debug(f"Преобразование mode: '{mode}' -> '{api_mode}' для KLING API")
	
	return api_mode


def _generate_kling_jwt_token(access_key: str, secret_key: str) -> str:
	"""
	Генерирует JWT токен для авторизации в KLING API.
	
	Args:
		access_key: ACCESS_KEY для KLING API
		secret_key: SECRET_KEY для подписи JWT токена
		
	Returns:
		str: JWT токен (3 части: header.payload.signature)
		
	Raises:
		Exception: При ошибках генерации токена
	"""
	try:
		# Заголовок JWT
		headers = {
			"alg": "HS256",
			"typ": "JWT"
		}
		
		# Payload JWT
		current_time = int(time.time())
		payload = {
			"iss": access_key,  # Issuer - ACCESS_KEY
			"exp": current_time + 1800,  # Expiration - 30 минут
			"nbf": current_time - 5  # Not Before - 5 секунд назад
		}
		
		# Генерируем JWT токен с подписью SECRET_KEY
		token = jwt.encode(payload, secret_key, algorithm="HS256", headers=headers)
		
		return token
	except Exception as e:
		logger.error(f"Ошибка генерации JWT токена: {e}")
		raise Exception(f"Не удалось сгенерировать JWT токен: {e}") from e


def _calculate_max_wait_time(mode: str, duration: int) -> int:
	"""
	Рассчитывает максимальное время ожидания в секундах на основе сложности задачи.
	
	Args:
		mode: Режим генерации ("standard" для 720p или "pro" для 1080p)
		duration: Длительность видео в секундах (5 или 10)
		
	Returns:
		int: Максимальное время ожидания в секундах
	"""
	if duration == 5 and mode == "standard":
		return 300  # 5 минут - простые задачи
	elif duration == 5 and mode == "pro":
		return 420  # 7 минут - 1080p требует больше времени
	elif duration == 10 and mode == "standard":
		return 420  # 7 минут - длительность увеличивает время обработки
	else:  # duration == 10 and mode == "pro"
		return 600  # 10 минут - самые сложные задачи (10 сек, 1080p)


async def _enhance_animation_prompt(
	image_url: str,
	user_prompt: str,
	reference_video_url: str | None = None
) -> str:
	"""
	Улучшает промпт для анимации на основе анализа фото и промпта пользователя.
	
	Анализирует фото через Vision API, затем использует GPT для создания детального
	промпта с учетом движения, камеры, освещения и перспективы.
	
	Args:
		image_url: URL фотографии для анализа
		user_prompt: Промпт пользователя
		reference_video_url: URL reference video (опционально, для motion control)
		
	Returns:
		str: Улучшенный промпт с деталями о движении, камере, освещении
	"""
	logger.info(f"Улучшение промпта для анимации: оригинальный промпт={user_prompt[:100]}...")
	
	try:
		# Шаг 1: Анализ фото через Vision API
		analysis_prompt = (
			"Опиши детально это фото на русском языке. Особенно важно описать:\n"
			"- Объекты и люди на фото (поза, положение, выражение лица, одежда)\n"
			"- Освещение и атмосфера (направление света, качество, время суток)\n"
			"- Фон и окружение (детали фона, передний план)\n"
			"- Композиция и перспектива (угол съемки, расположение объектов)\n\n"
			"Описание должно быть детальным и структурированным, чтобы можно было точно воспроизвести анимацию."
		)
		
		image_description = await vision_analyze(image_url, analysis_prompt)
		logger.info(f"Фото проанализировано, описание: {image_description[:150]}... (длина: {len(image_description)})")
		
		# Обрезаем слишком длинные описания
		MAX_DESCRIPTION_LENGTH = 2000
		if len(image_description) > MAX_DESCRIPTION_LENGTH:
			trimmed = image_description[:MAX_DESCRIPTION_LENGTH]
			last_period = trimmed.rfind('.')
			if last_period > MAX_DESCRIPTION_LENGTH * 0.8:
				image_description = trimmed[:last_period + 1]
			else:
				image_description = trimmed + "..."
			logger.info(f"Описание обрезано до {len(image_description)} символов")
		
		# Шаг 2: Улучшение промпта через GPT
		system_prompt = (
			"Ты эксперт по созданию детальных промптов для анимации изображений через AI. "
			"Твоя задача - создать идеальный промпт для анимации на основе описания фото и запроса пользователя.\n\n"
			"Создай детальный промпт на русском языке, который включает:\n"
			"1. Описание движения - что именно движется и как (плавно, естественно, динамично)\n"
			"2. Детали камеры - угол съемки, движение камеры (если нужно), перспектива\n"
			"3. Освещение и атмосфера - направление света, качество, настроение\n"
			"4. Детали объектов и людей - как они должны двигаться, сохраняя узнаваемость\n"
			"5. Оригинальный запрос пользователя - обязательно включи его в промпт\n\n"
			"Промпт должен быть конкретным, детальным и структурированным. "
			"Используй профессиональную терминологию для описания движения и камеры. "
			"Промпт должен быть на русском языке и не превышать 500 слов."
		)
		
		user_message = (
			f"Описание фото:\n{image_description}\n\n"
			f"Запрос пользователя для анимации:\n{user_prompt}\n\n"
		)
		
		if reference_video_url:
			user_message += "Примечание: будет использоваться reference video для точного переноса движений.\n\n"
		
		user_message += (
			"Создай идеальный промпт для анимации этого фото, учитывая все детали из описания "
			"и запрос пользователя. Промпт должен быть детальным и профессиональным."
		)
		
		messages = [
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": user_message}
		]
		
		enhanced_prompt = await chat_completion(messages, model="gpt-5-mini")
		enhanced_prompt = enhanced_prompt.strip()
		
		logger.info(f"Промпт улучшен: оригинальный ({len(user_prompt)} символов) -> улучшенный ({len(enhanced_prompt)} символов)")
		logger.debug(f"Улучшенный промпт: {enhanced_prompt[:200]}...")
		
		return enhanced_prompt
		
	except Exception as exc:
		logger.exception(f"Ошибка улучшения промпта: {exc}, используем оригинальный промпт")
		# В случае ошибки возвращаем оригинальный промпт
		return user_prompt


async def _prepare_auth_headers() -> dict[str, str]:
	"""
	Подготавливает заголовки с аутентификацией для KLING API.
	
	Returns:
		dict: Заголовки с Authorization
		
	Raises:
		Exception: При ошибках генерации токена или отсутствии ключей
	"""
	# Получаем и проверяем ключи для генерации JWT токена
	raw_access_key = settings.kling_access_key or ""
	access_key = raw_access_key.strip()
	
	raw_secret_key = settings.kling_secret_key or ""
	secret_key = raw_secret_key.strip()
	
	# Проверяем наличие ACCESS_KEY
	if not access_key:
		logger.error(
			f"KLING_ACCESS_KEY не установлен или пустой! "
			f"raw_value={repr(raw_access_key[:20]) if raw_access_key else 'None'}, "
			f"stripped_value={repr(access_key)}"
		)
		raise Exception("KLING_ACCESS_KEY не установлен в переменных окружения")
	
	# Проверяем наличие SECRET_KEY
	if not secret_key:
		logger.error(
			f"KLING_SECRET_KEY не установлен или пустой! "
			f"raw_value={repr(raw_secret_key[:20]) if raw_secret_key else 'None'}, "
			f"stripped_value={repr(secret_key)}"
		)
		raise Exception("KLING_SECRET_KEY не установлен в переменных окружения")
	
	# Логируем информацию о ключах (без вывода самих ключей)
	access_key_length = len(access_key)
	secret_key_length = len(secret_key)
	access_key_preview = f"{access_key[:4]}...{access_key[-4:]}" if access_key_length > 8 else "***"
	logger.info(f"✅ KLING ключи загружены: ACCESS_KEY длина={access_key_length}, превью={access_key_preview}, SECRET_KEY длина={secret_key_length}")
	
	# Генерируем JWT токен для авторизации
	logger.info("Генерация JWT токена для KLING API...")
	jwt_token = _generate_kling_jwt_token(access_key, secret_key)
	
	# Проверяем, что JWT токен состоит из 3 частей (header.payload.signature)
	jwt_parts = jwt_token.split('.')
	if len(jwt_parts) != 3:
		logger.error(f"ОШИБКА: JWT токен должен состоять из 3 частей, получено {len(jwt_parts)}")
		raise Exception(f"Неверный формат JWT токена: ожидается 3 части, получено {len(jwt_parts)}")
	
	# Логируем информацию о JWT токене (без вывода самого токена)
	jwt_length = len(jwt_token)
	jwt_preview = f"{jwt_token[:10]}...{jwt_token[-10:]}" if jwt_length > 20 else "***"
	logger.info(f"✅ JWT токен сгенерирован: длина={jwt_length}, превью={jwt_preview}, частей={len(jwt_parts)}")
	
	# Подготавливаем заголовки для аутентификации
	headers = {
		"Content-Type": "application/json",
	}
	
	# Добавляем аутентификацию согласно документации
	auth_header_value = f"Bearer {jwt_token}"
	headers["Authorization"] = auth_header_value
	
	# Логируем факт установки заголовка (без вывода самого токена)
	logger.debug(f"Заголовок Authorization установлен: длина={len(auth_header_value)}, превью=Bearer {jwt_preview}")
	
	return headers


async def _wait_for_video_ready(
	client: httpx.AsyncClient,
	headers: dict[str, str],
	task_id: str,
	status_url_template: str,
	mode: str,
	duration: int
) -> str:
	"""
	Ожидает готовности видео, проверяя статус задачи.
	
	Args:
		client: HTTP клиент
		headers: Заголовки запроса
		task_id: ID задачи
		status_url_template: Шаблон URL для проверки статуса (с {task_id})
		mode: Режим генерации
		duration: Длительность видео
		
	Returns:
		str: URL готового видео
		
	Raises:
		Exception: При ошибках или превышении времени ожидания
	"""
	check_interval = 1  # Проверяем каждую 1 секунду
	max_wait_time = _calculate_max_wait_time(mode, duration)
	max_attempts = max_wait_time // check_interval
	start_time = time.time()
	
	logger.info(
		f"Начало ожидания готовности видео: task_id={task_id}, "
		f"режим={mode}, длительность={duration}с, "
		f"максимум попыток={max_attempts}, интервал={check_interval}с, "
		f"максимальное время ожидания={max_wait_time}с ({max_wait_time // 60} минут)"
	)
	
	for attempt in range(max_attempts):
		# Первая проверка сразу, без задержки
		if attempt > 0:
			await asyncio.sleep(check_interval)
		
		elapsed_time = int(time.time() - start_time)
		progress_percent = int((attempt + 1) / max_attempts * 100)
		
		# Запрос статуса задачи
		status_url = status_url_template.format(task_id=task_id)
		
		try:
			status_response = await client.get(status_url, headers=headers)
			status_response.raise_for_status()
			status_result = status_response.json()
		except Exception as e:
			logger.error(
				f"Ошибка при запросе статуса задачи {task_id} "
				f"(попытка {attempt + 1}/{max_attempts}, время: {elapsed_time}с): {e}"
			)
			continue
		
		# Проверяем код ответа
		if status_result.get("code") != 0:
			error_msg = status_result.get("message", "Неизвестная ошибка")
			logger.warning(
				f"Ошибка при проверке статуса задачи {task_id} "
				f"(попытка {attempt + 1}/{max_attempts}, время: {elapsed_time}с, "
				f"код {status_result.get('code')}): {error_msg}. "
				f"Полный ответ API: {status_result}"
			)
			continue
		
		status_data = status_result.get("data", {})
		current_status = status_data.get("task_status", "processing")
		
		# Детальное логирование статуса
		logger.info(
			f"Статус задачи {task_id}: "
			f"попытка {attempt + 1}/{max_attempts} ({progress_percent}%), "
			f"время ожидания: {elapsed_time}с, "
			f"статус: {current_status}"
		)
		
		# Логируем полный ответ при статусе succeed или failed
		if current_status in ("succeed", "failed"):
			logger.info(f"Полный ответ API для задачи {task_id} (статус {current_status}): {status_result}")
		
		if current_status == "succeed":
			# Извлекаем URL видео
			video_url = None
			
			# Проверяем правильную структуру: data.task_result.videos[0].url
			task_result = status_data.get("task_result", {})
			if task_result:
				videos = task_result.get("videos", [])
				if videos and len(videos) > 0:
					first_video = videos[0]
					if isinstance(first_video, dict):
						video_url = first_video.get("url")
						if video_url:
							logger.info(
								f"✅ Видео готово для задачи {task_id}: "
								f"время ожидания: {elapsed_time}с, "
								f"попыток: {attempt + 1}/{max_attempts}, "
								f"URL найден в task_result.videos[0].url: {video_url[:100]}..."
							)
							return video_url
			
			# Проверяем альтернативные варианты
			if not video_url:
				video_url = (
					status_data.get("video_url") or 
					status_data.get("video") or 
					status_data.get("result_url") or
					status_data.get("result") or
					status_data.get("output_url") or
					status_data.get("url")
				)
			
			if video_url:
				logger.info(
					f"✅ Видео готово для задачи {task_id}: "
					f"время ожидания: {elapsed_time}с, "
					f"попыток: {attempt + 1}/{max_attempts}, "
					f"URL найден в альтернативном поле: {video_url[:100]}..."
				)
				return video_url
			else:
				logger.error(
					f"❌ Статус 'succeed' для задачи {task_id}, но video_url не найден. "
					f"Полный ответ data: {status_data}"
				)
		
		if current_status == "failed":
			error_msg = (
				status_data.get("task_status_msg") or 
				status_data.get("error") or 
				status_data.get("error_message") or
				status_data.get("message") or
				"Неизвестная ошибка"
			)
			logger.error(
				f"❌ Генерация видео не удалась для задачи {task_id}: "
				f"время ожидания: {elapsed_time}с, "
				f"попыток: {attempt + 1}/{max_attempts}, "
				f"ошибка: {error_msg}. "
				f"Полный ответ API: {status_result}"
			)
			raise Exception(f"Генерация видео не удалась: {error_msg}")
		
		# Статусы "submitted" и "processing" - продолжаем ждать
		if (attempt + 1) % 30 == 0:
			logger.info(
				f"⏳ Ожидание готовности видео для задачи {task_id}: "
				f"прошло {elapsed_time}с ({progress_percent}%), "
				f"текущий статус: {current_status}, "
				f"осталось попыток: {max_attempts - attempt - 1}"
			)
	
	elapsed_time = int(time.time() - start_time)
	logger.error(
		f"❌ Превышено время ожидания генерации видео для задачи {task_id}: "
		f"прошло {elapsed_time}с, "
		f"выполнено попыток: {max_attempts}/{max_attempts}"
	)
	raise Exception(f"Превышено время ожидания генерации видео ({elapsed_time}с)")


async def _animate_photo_kling_v26(
	image_url: str,
	reference_video_url: str,
	description: str,
	mode: Literal["standard", "pro"],
	duration: Literal[5, 10],
	motion_direction: str = "video_direction"
) -> str:
	"""
	Оживляет фото с использованием Kling 2.6 Motion Control для точного переноса движений.
	
	Args:
		image_url: URL фотографии для оживления
		reference_video_url: URL примера видео
		description: Текстовое описание того, как нужно оживить фото
		mode: Режим генерации ("standard" для 720p или "pro" для 1080p)
		duration: Длительность видео в секундах (5 или 10)
		motion_direction: Направление движения ("image_direction" или "video_direction")
		
	Returns:
		str: URL готового видео
		
	Raises:
		Exception: При ошибках API или обработки
	"""
	logger.info(
		f"Использование Kling 2.6 Motion Control: image_url={image_url[:50]}..., "
		f"reference_video_url={reference_video_url[:50]}..., "
		f"mode={mode}, duration={duration}s, motion_direction={motion_direction}"
	)
	
	# Улучшаем промпт для лучшего качества анимации
	enhanced_description = await _enhance_animation_prompt(
		image_url=image_url,
		user_prompt=description,
		reference_video_url=reference_video_url
	)
	logger.info(f"Промпт улучшен: оригинальный='{description[:100]}...' -> улучшенный='{enhanced_description[:100]}...'")
	
	# Пробуем разные варианты endpoints для Kling 2.6
	endpoints_to_try = [
		f"{settings.kling_api_base_url}/videos/motion-create",
		f"{settings.kling_api_base_url}/api/v1/jobs/createTask",
	]
	
	# Преобразуем mode
	api_mode = _map_mode_to_api(mode)
	
	# Подготавливаем заголовки
	headers = await _prepare_auth_headers()
	
	# Пробуем разные форматы payload
	payloads_to_try = [
		# Формат 1: с model_name (ближе к текущему формату)
		{
			"model_name": "kling-2.6/motion-control",
			"image": image_url,
			"reference_video": reference_video_url,
			"prompt": enhanced_description,
			"mode": api_mode,
			"duration": str(duration),
			"motionDirection": motion_direction
		},
		# Формат 2: с model и input (стандартный формат для motion-control)
		{
			"model": "kling-2.6/motion-control",
			"input": {
				"prompt": enhanced_description,
				"input_urls": [image_url],
				"video_urls": [reference_video_url],
				"mode": "720p" if mode == "standard" else "1080p",
				"motionDirection": motion_direction
			}
		},
		# Формат 3: альтернативный с motionUrl
		{
			"model_name": "kling-2.6/motion-control",
			"imageUrl": image_url,
			"motionUrl": reference_video_url,
			"prompt": enhanced_description,
			"mode": api_mode,
			"duration": str(duration),
			"motionDirection": motion_direction
		}
	]
	
	async with httpx.AsyncClient(timeout=300.0) as client:
		for endpoint in endpoints_to_try:
			if not endpoint.startswith("http"):
				endpoint = f"https://{endpoint}"
			
			for payload in payloads_to_try:
				try:
					logger.info(f"Попытка запроса к {endpoint} с payload форматом {payload.get('model_name') or payload.get('model')}")
					logger.debug(f"Payload: {payload}")
					
					response = await client.post(endpoint, json=payload, headers=headers)
					response.raise_for_status()
					
					result = response.json()
					logger.info(f"Ответ от KLING API получен: {result}")
					
					# Проверяем код ответа (0 = успех)
					if result.get("code") != 0:
						error_msg = result.get("message", "Неизвестная ошибка")
						logger.warning(f"Ошибка API (код {result.get('code')}): {error_msg}, пробую следующий формат")
						continue
					
					# Получаем данные из ответа
					data = result.get("data", {})
					if not data:
						# Может быть другой формат ответа
						data = result
					
					task_id = data.get("task_id") or data.get("job_id") or data.get("id")
					if not task_id:
						logger.warning("Не получен task_id от API, пробую следующий формат")
						continue
					
					task_status = data.get("task_status") or data.get("status", "submitted")
					logger.info(f"Задача создана, task_id: {task_id}, статус: {task_status}")
					
					# Если задача уже выполнена сразу
					if task_status == "succeed" or task_status == "completed":
						video_url = None
						task_result = data.get("task_result", {})
						if task_result:
							videos = task_result.get("videos", [])
							if videos and len(videos) > 0:
								first_video = videos[0]
								if isinstance(first_video, dict):
									video_url = first_video.get("url")
						
						if not video_url:
							video_url = (
								data.get("video_url") or 
								data.get("video") or 
								data.get("result_url") or
								data.get("result")
							)
						
						if video_url:
							logger.info(f"✅ Видео готово сразу после создания задачи: {video_url[:100]}...")
							return video_url
					
					# Определяем URL для проверки статуса
					# Если endpoint содержит /jobs/createTask, статус может быть в другом месте
					if "/jobs/createTask" in endpoint or "/api/v1/jobs/createTask" in endpoint:
						status_url_template = f"{settings.kling_api_base_url}/api/v1/jobs/{task_id}"
					elif "/motion-create" in endpoint:
						status_url_template = f"{settings.kling_api_base_url}/videos/motion-create/{task_id}"
					else:
						# Fallback на стандартный формат
						status_url_template = f"{endpoint}/{task_id}"
					
					# Ожидаем готовности видео
					return await _wait_for_video_ready(
						client, headers, task_id, status_url_template, mode, duration
					)
					
				except httpx.HTTPStatusError as e:
					logger.warning(f"HTTP ошибка {e.response.status_code} для {endpoint}, пробую следующий формат")
					continue
				except Exception as e:
					logger.warning(f"Ошибка для {endpoint}: {e}, пробую следующий формат")
					continue
		
		# Если все варианты не сработали
		raise Exception("Не удалось создать задачу через Kling 2.6 Motion Control. Все варианты endpoints и payload не сработали.")


async def _animate_photo_image2video(
	image_url: str,
	description: str,
	mode: Literal["standard", "pro"],
	duration: Literal[5, 10]
) -> str:
	"""
	Оживляет фото без motion control через стандартный image2video endpoint.
	
	Args:
		image_url: URL фотографии для оживления
		description: Текстовое описание того, как нужно оживить фото
		mode: Режим генерации ("standard" для 720p или "pro" для 1080p)
		duration: Длительность видео в секундах (5 или 10)
		
	Returns:
		str: URL готового видео
		
	Raises:
		Exception: При ошибках API или обработки
	"""
	logger.info(
		f"Использование стандартного image2video: image_url={image_url[:50]}..., "
		f"mode={mode}, duration={duration}s"
	)
	
	# Улучшаем промпт для лучшего качества анимации
	enhanced_description = await _enhance_animation_prompt(
		image_url=image_url,
		user_prompt=description,
		reference_video_url=None
	)
	logger.info(f"Промпт улучшен: оригинальный='{description[:100]}...' -> улучшенный='{enhanced_description[:100]}...'")
	
	# Формируем URL API
	api_url = f"{settings.kling_api_base_url}/videos/image2video"
	if not api_url.startswith("http"):
		api_url = f"https://{api_url}"
	
	# Подготавливаем заголовки
	headers = await _prepare_auth_headers()
	
	# Преобразуем mode
	api_mode = _map_mode_to_api(mode)
	
	# Подготавливаем тело запроса
	payload = {
		"model_name": "kling-v1",
		"mode": api_mode,
		"duration": str(duration),
		"image": image_url,
		"prompt": enhanced_description,
	}
	
	logger.info(f"Отправка запроса в KLING API: {api_url}")
	logger.debug(f"Payload: {payload}")
	
	async with httpx.AsyncClient(timeout=300.0) as client:
		try:
			response = await client.post(api_url, json=payload, headers=headers)
			response.raise_for_status()
			
			result = response.json()
			logger.info(f"Ответ от KLING API получен: {result}")
			
			# Проверяем код ответа (0 = успех)
			if result.get("code") != 0:
				error_msg = result.get("message", "Неизвестная ошибка")
				raise Exception(f"Ошибка API (код {result.get('code')}): {error_msg}")
			
			# Получаем данные из ответа
			data = result.get("data", {})
			if not data:
				raise Exception("Пустой ответ от API (нет поля data)")
			
			task_id = data.get("task_id")
			if not task_id:
				raise Exception("Не получен task_id от API")
			
			task_status = data.get("task_status", "submitted")
			logger.info(f"Задача создана, task_id: {task_id}, статус: {task_status}")
			
			# Если задача уже выполнена сразу
			if task_status == "succeed":
				video_url = None
				task_result = data.get("task_result", {})
				if task_result:
					videos = task_result.get("videos", [])
					if videos and len(videos) > 0:
						first_video = videos[0]
						if isinstance(first_video, dict):
							video_url = first_video.get("url")
				
				if not video_url:
					video_url = data.get("video_url") or data.get("video") or data.get("result_url")
				
				if video_url:
					logger.info(f"✅ Видео готово сразу после создания задачи: {video_url[:100]}...")
					return video_url
			
			# Ожидаем готовности видео
			status_url_template = f"{settings.kling_api_base_url}/videos/image2video/{task_id}"
			return await _wait_for_video_ready(
				client, headers, task_id, status_url_template, mode, duration
			)
			
		except httpx.HTTPStatusError as e:
			error_text = e.response.text if e.response else "Нет деталей ошибки"
			error_headers = dict(e.response.headers) if e.response else {}
			logger.error(
				f"❌ Ошибка HTTP от KLING-V2 API: "
				f"статус={e.response.status_code}, "
				f"URL={api_url}, "
				f"заголовки ответа={error_headers}, "
				f"тело ответа={error_text[:500]}"
			)
			raise Exception(f"Ошибка API: {e.response.status_code} - {error_text[:200]}") from e
		except httpx.RequestError as e:
			logger.error(
				f"❌ Ошибка подключения к KLING-V2 API: "
				f"URL={api_url}, "
				f"ошибка={e}, "
				f"тип={type(e).__name__}"
			)
			raise Exception(f"Не удалось подключиться к API: {e}") from e
		except Exception as e:
			logger.exception(
				f"❌ Неожиданная ошибка при работе с KLING-V2 API: "
				f"тип={type(e).__name__}, "
				f"ошибка={e}, "
				f"URL={api_url}"
			)
			raise


async def animate_photo(
	image_url: str,
	reference_video_url: str | None,
	description: str,
	mode: Literal["standard", "pro"],
	duration: Literal[5, 10],
	motion_direction: str = "video_direction"
) -> str:
	"""
	Оживляет фото с использованием примера видео (опционально) через KLING-V2 API.
	
	Использует Kling 2.6 Motion Control для точного переноса движений, если предоставлен reference_video_url.
	Иначе использует стандартный image2video метод.
	
	Args:
		image_url: URL фотографии для оживления
		reference_video_url: URL примера видео (опционально, может быть None)
		description: Текстовое описание того, как нужно оживить фото
		mode: Режим генерации ("standard" для 720p или "pro" для 1080p)
		duration: Длительность видео в секундах (5 или 10)
		motion_direction: Направление движения ("image_direction" или "video_direction")
	
	Returns:
		str: URL готового видео или путь к файлу
	
	Raises:
		Exception: При ошибках API или обработки
	"""
	# Безопасное форматирование reference_video_url для логирования
	reference_video_preview = (
		(reference_video_url[:50] + "..." if len(reference_video_url) > 50 else reference_video_url)
		if reference_video_url else "None"
	)
	logger.info(
		f"Начало оживления фото: image_url={image_url[:50]}..., "
		f"reference_video_url={reference_video_preview}, "
		f"mode={mode}, duration={duration}s, motion_direction={motion_direction}"
	)
	
	if reference_video_url:
		# Используем Kling 2.6 Motion Control для точного переноса движений
		logger.info("Использование Kling 2.6 Motion Control для точного переноса движений из reference video")
		return await _animate_photo_kling_v26(
			image_url=image_url,
			reference_video_url=reference_video_url,
			description=description,
			mode=mode,
			duration=duration,
			motion_direction=motion_direction
		)
	else:
		# Используем стандартный image2video метод (без motion control)
		logger.info("Использование стандартного image2video метода (без motion control)")
		return await _animate_photo_image2video(
			image_url=image_url,
			description=description,
			mode=mode,
			duration=duration
		)
