"""
Сервис для генерации изображений через OpenAI DALL-E 3 API.
"""
import httpx
from loguru import logger
from app.config import get_settings
from app.utils.openai_client import create_openai_client
from app.services.llm import vision_analyze
from openai import OpenAI

__all__ = ["generate_image", "create_edit_prompt"]

settings = get_settings()
http_client = create_openai_client()
client = OpenAI(api_key=settings.openai_api_key, http_client=http_client)


def _get_image_size(format: str) -> str:
	"""
	Преобразует формат в размер для DALL-E 3.
	
	Args:
		format: Формат изображения (1:1, 2:3, 3:2)
	
	Returns:
		str: Размер для DALL-E 3 API
	"""
	format_map = {
		"1:1": "1024x1024",
		"2:3": "1024x1792",  # Исправлено: было 1024x1536
		"3:2": "1792x1024",  # Исправлено: было 1536x1024
	}
	return format_map.get(format, "1024x1024")


async def create_edit_prompt(original_image_url: str, edit_instructions: str) -> str:
	"""
	Создает улучшенный промпт для редактирования изображения на основе анализа исходного фото.
	
	Args:
		original_image_url: URL исходного изображения для анализа
		edit_instructions: Инструкции пользователя по изменениям
	
	Returns:
		str: Улучшенный промпт для генерации с учетом исходного фото
	"""
	logger.info(f"Создание промпта для редактирования: анализ фото {original_image_url[:50]}...")
	
	# Анализируем исходное фото через Vision API
	# Промпт запрашивает детальное описание в формате, похожем на пример заказчика
	analysis_prompt = (
		"Опиши детально это фото на русском языке в следующем формате:\n\n"
		'"На фото — [детальное описание человека: внешность, черты лица (форма лица, структура лица, глаза, нос, рот, подбородок, скулы, брови), '
		'прическа, макияж, выражение лица, одежда и аксессуары (детально - костюм, рубашка, галстук, аксессуары), '
		'поза и положение тела, положение рук и жесты].\n\n'
		'На заднем плане — [детальное описание фона: природа, здания, небо, облака, деревья, холмы, застройка, скалистые выемки и т.д.].\n\n'
		'На переднем плане — [описание переднего плана: перила, ограждения, предметы и т.д.].\n\n'
		'Освещение [описание освещения: тёплое, холодное, направление света], фото сделано [время суток/условия: днём, утром, вечером, в ясный солнечный день и т.д.]."\n\n'
		"Особенно важно детально описать черты лица, форму лица, структуру лица, глаза, нос, рот, подбородок, скулы, "
		"чтобы их можно было точно воспроизвести в новом изображении. Описание должно быть максимально подробным и структурированным."
	)
	
	try:
		image_description = await vision_analyze(original_image_url, analysis_prompt)
		logger.info(f"Фото проанализировано, описание: {image_description[:100]}... (длина: {len(image_description)})")
		
		# Обрезаем слишком длинные описания от Vision API (лимит ~3000 символов для описания)
		# чтобы оставить место для остальной части промпта (около 1000 символов)
		MAX_DESCRIPTION_LENGTH = 3000
		if len(image_description) > MAX_DESCRIPTION_LENGTH:
			logger.warning(f"Описание от Vision API слишком длинное ({len(image_description)} символов), обрезаю до {MAX_DESCRIPTION_LENGTH}")
			# Обрезаем до последнего полного предложения в пределах лимита
			trimmed = image_description[:MAX_DESCRIPTION_LENGTH]
			last_period = trimmed.rfind('.')
			if last_period > MAX_DESCRIPTION_LENGTH * 0.8:  # Если точка найдена в последних 20%
				image_description = trimmed[:last_period + 1]
			else:
				image_description = trimmed + "..."
			logger.info(f"Описание обрезано до {len(image_description)} символов")
	except Exception as exc:
		logger.exception(f"Ошибка анализа фото через Vision API: {exc}")
		# Если анализ не удался, используем базовый промпт
		image_description = "исходное фото"
	
	# Создаем улучшенный промпт для DALL-E
	# Промпт должен четко разделять что сохранять (черты лица, идентичность) и что изменять (по инструкциям пользователя)
	enhanced_prompt = (
		f"Create a professional portrait photo.\n\n"
		f"Based on this original photo description: {image_description}\n\n"
		f"Apply these specific changes requested by the user: {edit_instructions}\n\n"
		f"CRITICAL REQUIREMENTS - MUST PRESERVE:\n"
		f"- Keep the EXACT same facial features: face shape, facial structure, eye shape and color, nose shape, mouth shape, chin shape, cheekbones structure, eyebrow shape and position\n"
		f"- Preserve the person's unique identity - the person must look like the EXACT same person from the original photo\n"
		f"- Keep the same pose and body position from the original photo\n"
		f"- Keep the same expression and overall appearance of the person\n"
		f"- Maintain the same professional quality, composition, and lighting style as the original photo\n\n"
		f"ONLY modify these elements as specified in the user's changes:\n"
		f"- Background (if requested in user's instructions)\n"
		f"- Clothing and accessories (if requested in user's instructions)\n"
		f"- Styling elements (if requested in user's instructions)\n"
		f"- Other elements explicitly mentioned in the user's instructions\n\n"
		f"The person must look like the same person from the original photo, only with the requested modifications applied."
	)
	
	# Проверяем длину финального промпта (лимит DALL-E 3: 4000 символов)
	DALL_E_MAX_PROMPT_LENGTH = 4000
	if len(enhanced_prompt) > DALL_E_MAX_PROMPT_LENGTH:
		logger.warning(f"Промпт превышает лимит DALL-E 3 ({len(enhanced_prompt)} > {DALL_E_MAX_PROMPT_LENGTH}), обрезаю описание")
		# Вычисляем сколько символов нужно обрезать из описания
		excess = len(enhanced_prompt) - DALL_E_MAX_PROMPT_LENGTH
		# Обрезаем описание, оставляя место для остальной части промпта
		base_prompt_length = len(enhanced_prompt) - len(image_description)
		max_description_length = DALL_E_MAX_PROMPT_LENGTH - base_prompt_length - 100  # Запас 100 символов
		
		if max_description_length > 0:
			# Обрезаем до последнего полного предложения
			trimmed_desc = image_description[:max_description_length]
			last_period = trimmed_desc.rfind('.')
			if last_period > max_description_length * 0.8:
				image_description = trimmed_desc[:last_period + 1]
			else:
				image_description = trimmed_desc + "..."
			
			# Пересоздаем промпт с обрезанным описанием
			enhanced_prompt = (
				f"Create a professional portrait photo.\n\n"
				f"Based on this original photo description: {image_description}\n\n"
				f"Apply these specific changes requested by the user: {edit_instructions}\n\n"
				f"CRITICAL REQUIREMENTS - MUST PRESERVE:\n"
				f"- Keep the EXACT same facial features: face shape, facial structure, eye shape and color, nose shape, mouth shape, chin shape, cheekbones structure, eyebrow shape and position\n"
				f"- Preserve the person's unique identity - the person must look like the EXACT same person from the original photo\n"
				f"- Keep the same pose and body position from the original photo\n"
				f"- Keep the same expression and overall appearance of the person\n"
				f"- Maintain the same professional quality, composition, and lighting style as the original photo\n\n"
				f"ONLY modify these elements as specified in the user's changes:\n"
				f"- Background (if requested in user's instructions)\n"
				f"- Clothing and accessories (if requested in user's instructions)\n"
				f"- Styling elements (if requested in user's instructions)\n"
				f"- Other elements explicitly mentioned in the user's instructions\n\n"
				f"The person must look like the same person from the original photo, only with the requested modifications applied."
			)
			logger.warning(f"Промпт обрезан до {len(enhanced_prompt)} символов")
		else:
			logger.error(f"Невозможно обрезать промпт: базовая часть ({base_prompt_length}) превышает лимит ({DALL_E_MAX_PROMPT_LENGTH})")
	
	logger.info(f"Создан улучшенный промпт для редактирования (длина: {len(enhanced_prompt)})")
	return enhanced_prompt


async def generate_image(
	prompt: str,
	image_urls: list[str] | None = None,
	format: str = "1:1",
	edit_mode: bool = False
) -> bytes:
	"""
	Генерирует изображение через OpenAI DALL-E 3 API.
	
	Args:
		prompt: Текстовый запрос для генерации
		image_urls: Список URL изображений для использования в качестве референса (до 3)
		format: Формат изображения (1:1, 2:3, 3:2)
		edit_mode: Если True, промпт уже содержит улучшенное описание для редактирования
	
	Returns:
		bytes: Сгенерированное изображение в формате PNG
	"""
	logger.info(f"Начало генерации изображения: prompt={prompt[:50]}..., format={format}, images={len(image_urls) if image_urls else 0}, edit_mode={edit_mode}")
	
	# DALL-E 3 не поддерживает референсные изображения напрямую
	# Если есть референсные изображения, упоминаем их в промпте
	enhanced_prompt = prompt
	if image_urls and not edit_mode:
		# В режиме редактирования промпт уже содержит описание исходного фото
		enhanced_prompt = f"{prompt} (Inspired by the reference images provided by the user)"
	
	# Валидация промпта перед отправкой в API
	if not enhanced_prompt or not enhanced_prompt.strip():
		raise ValueError("Промпт не может быть пустым")
	
	DALL_E_MAX_PROMPT_LENGTH = 4000
	if len(enhanced_prompt) > DALL_E_MAX_PROMPT_LENGTH:
		logger.warning(f"Промпт превышает лимит DALL-E 3 ({len(enhanced_prompt)} > {DALL_E_MAX_PROMPT_LENGTH}), обрезаю до {DALL_E_MAX_PROMPT_LENGTH}")
		# Обрезаем до последнего полного слова в пределах лимита
		trimmed = enhanced_prompt[:DALL_E_MAX_PROMPT_LENGTH]
		last_space = trimmed.rfind(' ')
		if last_space > DALL_E_MAX_PROMPT_LENGTH * 0.9:  # Если пробел найден в последних 10%
			enhanced_prompt = trimmed[:last_space]
		else:
			enhanced_prompt = trimmed
		logger.warning(f"Промпт обрезан до {len(enhanced_prompt)} символов")
	
	logger.info(f"Валидация промпта пройдена, длина: {len(enhanced_prompt)} символов")
	
	# Генерируем изображение через DALL-E 3
	try:
		response = client.images.generate(
			model="dall-e-3",
			prompt=enhanced_prompt,
			size=_get_image_size(format),
			quality="standard",
			n=1,
		)
		
		image_url = response.data[0].url
		logger.info(f"Изображение сгенерировано, URL: {image_url}")
		
		# Загружаем сгенерированное изображение
		async with httpx.AsyncClient(timeout=30.0) as http_client:
			response_img = await http_client.get(image_url)
			response_img.raise_for_status()
			image_bytes = response_img.content
		
		logger.info(f"Генерация изображения завершена, размер: {len(image_bytes)} bytes")
		return image_bytes
		
	except Exception as exc:
		# Детальное логирование ошибки для диагностики
		error_type = type(exc).__name__
		error_message = str(exc)
		prompt_length = len(enhanced_prompt)
		
		logger.error(
			f"Ошибка генерации изображения: "
			f"тип={error_type}, "
			f"сообщение={error_message}, "
			f"длина_промпта={prompt_length}, "
			f"format={format}, "
			f"edit_mode={edit_mode}"
		)
		
		# Для ошибок OpenAI API логируем дополнительную информацию
		if hasattr(exc, 'status_code'):
			logger.error(f"OpenAI API ошибка: status_code={exc.status_code}, response={getattr(exc, 'response', None)}")
		if hasattr(exc, 'body'):
			logger.error(f"OpenAI API body: {exc.body}")
		
		logger.exception("Полный traceback ошибки:")
		raise

