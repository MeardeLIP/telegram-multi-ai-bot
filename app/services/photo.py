"""
Сервисы для обработки фотографий: улучшение качества, замена фона, удаление фона.
"""
import httpx
import cv2
import numpy as np
from PIL import Image
import io
from loguru import logger
from app.config import get_settings
from app.utils.openai_client import create_openai_client
from openai import OpenAI

try:
	from rembg import remove
	REMBG_AVAILABLE = True
except ImportError:
	REMBG_AVAILABLE = False
	logger.warning("rembg не установлен. Функции замены и удаления фона будут недоступны.")

settings = get_settings()
http_client = create_openai_client()
client = OpenAI(api_key=settings.openai_api_key, http_client=http_client)


async def _download_image(url: str) -> np.ndarray:
	"""
	Загружает изображение по URL и возвращает его как numpy array (BGR формат для OpenCV).
	"""
	async with httpx.AsyncClient(timeout=30.0) as http_client:
		response = await http_client.get(url)
		response.raise_for_status()
		
		# Конвертируем bytes в numpy array
		image_bytes = np.frombuffer(response.content, np.uint8)
		image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
		
		if image is None:
			raise ValueError("Не удалось декодировать изображение")
		
		return image


def _encode_image_to_jpeg(image: np.ndarray, quality: int = 95) -> bytes:
	"""
	Кодирует изображение в JPEG формат.
	
	Args:
		image: Изображение в формате BGR (OpenCV)
		quality: Качество JPEG (0-100)
	
	Returns:
		bytes: Изображение в формате JPEG
	"""
	_, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, quality])
	return buffer.tobytes()


async def enhance_photo(image_url: str) -> bytes:
	"""
	Улучшает качество фотографии.
	
	Args:
		image_url: URL изображения для улучшения
	
	Returns:
		bytes: Улучшенное изображение в формате JPEG
	"""
	logger.info(f"Начало улучшения фото: {image_url}")
	
	# Загружаем изображение
	image = await _download_image(image_url)
	logger.info(f"Изображение загружено, shape={image.shape}")
	
	# Применяем улучшение качества (аналогично faceswap)
	# Улучшение контраста через CLAHE
	lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
	l, a, b = cv2.split(lab)
	clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
	l = clahe.apply(l)
	enhanced = cv2.merge([l, a, b])
	enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
	
	# Повышение резкости через unsharp mask
	gaussian = cv2.GaussianBlur(enhanced, (0, 0), 1.0)
	sharpened = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
	result = cv2.addWeighted(enhanced, 0.75, sharpened, 0.25, 0)
	
	# Легкая коррекция яркости и насыщенности
	hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
	h, s, v = cv2.split(hsv)
	s = cv2.add(s, int(255 * 0.05))
	s = np.clip(s, 0, 255).astype(np.uint8)
	v = cv2.add(v, int(255 * 0.02))
	v = np.clip(v, 0, 255).astype(np.uint8)
	result = cv2.merge([h, s, v])
	result = cv2.cvtColor(result, cv2.COLOR_HSV2BGR)
	
	# Конвертируем в JPEG
	image_bytes = _encode_image_to_jpeg(result, quality=95)
	logger.info(f"Улучшение фото завершено, размер результата: {len(image_bytes)} bytes")
	return image_bytes


async def _remove_background_mask(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
	"""
	Удаляет фон с изображения и возвращает объект с прозрачностью и маску.
	
	Args:
		image: Изображение в формате BGR (OpenCV)
	
	Returns:
		tuple: (изображение с прозрачностью в RGBA, маска альфа-канала)
	"""
	if not REMBG_AVAILABLE:
		raise ImportError("rembg не установлен. Установите: pip install rembg")
	
	# Конвертируем BGR в RGB для rembg
	image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
	
	# Конвертируем в PIL Image
	pil_image = Image.fromarray(image_rgb)
	
	# Удаляем фон через rembg
	output = remove(pil_image)
	
	# Конвертируем обратно в numpy array
	output_array = np.array(output)
	
	# Извлекаем альфа-канал (маску)
	if output_array.shape[2] == 4:
		mask = output_array[:, :, 3]  # Альфа-канал
		rgba_image = output_array
	else:
		# Если нет альфа-канала, создаём маску (все пиксели непрозрачны)
		mask = np.ones((output_array.shape[0], output_array.shape[1]), dtype=np.uint8) * 255
		rgba_image = np.dstack([output_array, mask])
	
	return rgba_image, mask


async def _generate_background(description: str, width: int, height: int) -> np.ndarray:
	"""
	Генерирует новый фон по описанию.
	
	Args:
		description: Описание фона на русском языке
		width: Ширина фона
		height: Высота фона
	
	Returns:
		np.ndarray: Изображение фона в формате RGB
	"""
	logger.info(f"Генерация фона: {description}, размер: {width}x{height}")
	
	try:
		# Пытаемся использовать DALL-E 3 для генерации фона
		# Переводим описание на английский для лучшего понимания моделью
		prompt = f"Background image: {description}. High quality, realistic, detailed background. No people, no objects, just background."
		
		response = client.images.generate(
			model="dall-e-3",
			prompt=prompt,
			size="1024x1024",  # DALL-E 3 поддерживает только 1024x1024
			quality="standard",
			n=1,
		)
		
		image_url = response.data[0].url
		
		# Загружаем сгенерированное изображение
		async with httpx.AsyncClient(timeout=30.0) as http_client:
			response_img = await http_client.get(image_url)
			response_img.raise_for_status()
			
			# Конвертируем в numpy array
			image_bytes = np.frombuffer(response_img.content, np.uint8)
			bg_image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
			
			if bg_image is None:
				raise ValueError("Не удалось декодировать сгенерированное изображение")
			
			# Конвертируем BGR в RGB
			bg_image_rgb = cv2.cvtColor(bg_image, cv2.COLOR_BGR2RGB)
			
			# Изменяем размер под нужные размеры
			bg_image_resized = cv2.resize(bg_image_rgb, (width, height), interpolation=cv2.INTER_LANCZOS4)
			
			logger.info(f"Фон сгенерирован через DALL-E, размер: {bg_image_resized.shape}")
			return bg_image_resized
			
	except Exception as exc:
		logger.warning(f"Не удалось сгенерировать фон через DALL-E: {exc}. Используем простую генерацию.")
		# Простая генерация фона по ключевым словам
		return _generate_simple_background(description, width, height)


def _generate_simple_background(description: str, width: int, height: int) -> np.ndarray:
	"""
	Генерирует простой фон по ключевым словам в описании.
	
	Args:
		description: Описание фона
		width: Ширина
		height: Высота
	
	Returns:
		np.ndarray: Изображение фона в RGB
	"""
	description_lower = description.lower()
	
	# Определяем тип фона по ключевым словам
	if any(word in description_lower for word in ["облака", "облако", "небо", "sky", "cloud"]):
		# Небо с облаками - градиент от голубого к белому
		bg = np.zeros((height, width, 3), dtype=np.uint8)
		for y in range(height):
			# Градиент от голубого (верх) к светло-голубому (низ)
			ratio = y / height
			bg[y, :] = [
				int(135 + (200 - 135) * ratio),  # R
				int(206 + (230 - 206) * ratio),  # G
				int(250),  # B
			]
		# Добавляем "облака" - белые размытые пятна
		for _ in range(5):
			x = np.random.randint(0, width)
			y = np.random.randint(0, height // 2)
			size = np.random.randint(100, 300)
			cv2.circle(bg, (x, y), size, (255, 255, 255), -1)
			bg = cv2.GaussianBlur(bg, (201, 201), 0)
		
	elif any(word in description_lower for word in ["пляж", "beach", "песок", "sand", "море", "sea", "океан", "ocean"]):
		# Пляж - градиент от неба к песку
		bg = np.zeros((height, width, 3), dtype=np.uint8)
		sky_height = height // 2
		for y in range(sky_height):
			ratio = y / sky_height
			bg[y, :] = [int(135 + (200 - 135) * ratio), int(206 + (230 - 206) * ratio), 250]
		for y in range(sky_height, height):
			bg[y, :] = [194, 178, 128]  # Песок
			
	elif any(word in description_lower for word in ["лес", "forest", "деревья", "trees", "зелень", "green"]):
		# Лес - зелёный градиент
		bg = np.zeros((height, width, 3), dtype=np.uint8)
		for y in range(height):
			ratio = y / height
			bg[y, :] = [
				int(34 + (60 - 34) * ratio),   # R
				int(139 + (120 - 139) * ratio),  # G
				int(34 + (50 - 34) * ratio),   # B
			]
			
	else:
		# По умолчанию - нейтральный градиент
		bg = np.zeros((height, width, 3), dtype=np.uint8)
		for y in range(height):
			ratio = y / height
			gray = int(200 + (150 - 200) * ratio)
			bg[y, :] = [gray, gray, gray]
	
	return bg


async def _combine_object_and_background(
	object_rgba: np.ndarray,
	mask: np.ndarray,
	background: np.ndarray
) -> np.ndarray:
	"""
	Объединяет объект без фона с новым фоном.
	
	Args:
		object_rgba: Объект с прозрачностью в формате RGBA
		mask: Маска альфа-канала
		background: Новый фон в формате RGB
	
	Returns:
		np.ndarray: Объединённое изображение в формате RGB
	"""
	# Нормализуем маску до 0-1
	mask_normalized = mask.astype(np.float32) / 255.0
	
	# Извлекаем RGB каналы объекта
	object_rgb = object_rgba[:, :, :3]
	
	# Применяем маску для смешивания
	result = np.zeros_like(background, dtype=np.float32)
	
	for c in range(3):
		result[:, :, c] = (
			object_rgb[:, :, c].astype(np.float32) * mask_normalized +
			background[:, :, c].astype(np.float32) * (1.0 - mask_normalized)
		)
	
	# Конвертируем обратно в uint8
	result = np.clip(result, 0, 255).astype(np.uint8)
	
	return result


async def replace_background(image_url: str, description: str) -> bytes:
	"""
	Заменяет фон на фотографии согласно описанию.
	
	Args:
		image_url: URL изображения
		description: Описание нового фона на русском языке
	
	Returns:
		bytes: Изображение с заменённым фоном в формате JPEG
	"""
	logger.info(f"Начало замены фона: {image_url}, описание: {description}")
	
	if not REMBG_AVAILABLE:
		raise ImportError("rembg не установлен. Установите: pip install rembg")
	
	# Загружаем изображение
	image = await _download_image(image_url)
	logger.info(f"Изображение загружено, shape={image.shape}")
	
	height, width = image.shape[:2]
	
	# Шаг 1: Удаляем фон и получаем объект с маской
	logger.info("Удаление фона...")
	object_rgba, mask = await _remove_background_mask(image)
	logger.info(f"Фон удалён, размер объекта: {object_rgba.shape}")
	
	# Шаг 2: Генерируем новый фон
	logger.info("Генерация нового фона...")
	background = await _generate_background(description, width, height)
	logger.info(f"Фон сгенерирован, размер: {background.shape}")
	
	# Шаг 3: Объединяем объект и новый фон
	logger.info("Объединение объекта и фона...")
	result_rgb = await _combine_object_and_background(object_rgba, mask, background)
	logger.info(f"Объект и фон объединены, размер: {result_rgb.shape}")
	
	# Конвертируем RGB в BGR для OpenCV
	result_bgr = cv2.cvtColor(result_rgb, cv2.COLOR_RGB2BGR)
	
	# Конвертируем в JPEG
	image_bytes = _encode_image_to_jpeg(result_bgr, quality=95)
	logger.info(f"Замена фона завершена, размер результата: {len(image_bytes)} bytes")
	return image_bytes


async def remove_background(image_url: str) -> bytes:
	"""
	Удаляет фон на фотографии, оставляя только основной объект.
	
	Args:
		image_url: URL изображения
	
	Returns:
		bytes: Изображение без фона (с прозрачным фоном) в формате PNG
	"""
	logger.info(f"Начало удаления фона: {image_url}")
	
	if not REMBG_AVAILABLE:
		raise ImportError("rembg не установлен. Установите: pip install rembg")
	
	# Загружаем изображение
	image = await _download_image(image_url)
	logger.info(f"Изображение загружено, shape={image.shape}")
	
	# Удаляем фон
	object_rgba, _ = await _remove_background_mask(image)
	logger.info(f"Фон удалён, размер объекта: {object_rgba.shape}")
	
	# Конвертируем RGBA в PIL Image для сохранения PNG
	pil_image = Image.fromarray(object_rgba, 'RGBA')
	
	# Сохраняем в PNG (поддерживает прозрачность)
	buffer = io.BytesIO()
	pil_image.save(buffer, format='PNG')
	image_bytes = buffer.getvalue()
	
	logger.info(f"Удаление фона завершено, размер результата: {len(image_bytes)} bytes")
	return image_bytes

