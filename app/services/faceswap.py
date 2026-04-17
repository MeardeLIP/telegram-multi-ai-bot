"""
Сервис для замены лиц на фотографиях через библиотеку insightface.
"""
from pathlib import Path
from typing import Optional

import cv2
import httpx
import numpy as np
import insightface
from insightface.app import FaceAnalysis
from loguru import logger

# Попытка импортировать GFPGAN для улучшения качества (опционально)
try:
	from gfpgan import GFPGANer
	GFPGAN_AVAILABLE = True
except ImportError:
	GFPGAN_AVAILABLE = False
	logger.info("GFPGAN не установлен. Будет использовано базовое улучшение качества.")

# Глобальные переменные для кэширования моделей
_face_analysis: Optional[FaceAnalysis] = None
_inswapper_model: Optional[object] = None
_gfpgan_model: Optional[object] = None


def _get_face_analysis() -> FaceAnalysis:
	"""
	Получает или создаёт экземпляр FaceAnalysis для детекции лиц.
	Использует CPU (ctx_id=-1).
	"""
	global _face_analysis
	if _face_analysis is None:
		logger.info("Инициализация FaceAnalysis для детекции лиц...")
		_face_analysis = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
		# Увеличиваем разрешение детекции для лучшего качества (1280x1280 - максимум для лучшей детекции)
		_face_analysis.prepare(ctx_id=-1, det_size=(1280, 1280))
		logger.info("FaceAnalysis инициализирован")
	return _face_analysis


def _get_inswapper_model():
	"""
	Получает или загружает модель inswapper для замены лиц.
	InsightFace автоматически скачает модель при первом использовании.
	
	Returns:
		Объект модели inswapper из insightface.model_zoo
	"""
	global _inswapper_model
	if _inswapper_model is None:
		logger.info("Загрузка модели inswapper_128.onnx...")
		try:
			model_path = Path.home() / ".insightface" / "models" / "inswapper_128.onnx"
			model_path.parent.mkdir(parents=True, exist_ok=True)

			_inswapper_model = insightface.model_zoo.get_model(
				"inswapper_128.onnx", download=True, download_zip=False
			)
			logger.info("Модель inswapper загружена успешно: %s", model_path)
		except Exception as exc:
			logger.exception("Ошибка загрузки модели inswapper: %s", exc)
			# Если автоматическая загрузка не сработала, выводим инструкции
			logger.warning(
				"Не удалось автоматически загрузить модель. "
				"Попробуйте скачать модель вручную в: %s",
				model_path
			)
			raise
	return _inswapper_model


async def _download_image(url: str) -> np.ndarray:
	"""
	Загружает изображение по URL и возвращает его как numpy array (BGR формат для OpenCV).
	"""
	async with httpx.AsyncClient(timeout=30.0) as client:
		response = await client.get(url)
		response.raise_for_status()
		
		# Конвертируем bytes в numpy array
		image_bytes = np.frombuffer(response.content, np.uint8)
		image = cv2.imdecode(image_bytes, cv2.IMREAD_COLOR)
		
		if image is None:
			raise ValueError("Не удалось декодировать изображение")
		
		return image


def _get_face_analysis_with_size(det_size: tuple = (1280, 1280)) -> FaceAnalysis:
	"""
	Создаёт экземпляр FaceAnalysis с указанным размером детекции.
	Используется для попыток с разными размерами детекции.
	"""
	app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
	app.prepare(ctx_id=-1, det_size=det_size)
	return app


def _detect_faces(image: np.ndarray) -> list:
	"""
	Обнаруживает лица на изображении с несколькими попытками и улучшениями.
	Возвращает список найденных лиц.
	"""
	h, w = image.shape[:2]
	max_dim = max(h, w)
	
	# Пробуем разные размеры детекции - иногда меньшие размеры работают лучше
	det_sizes = [(640, 640), (896, 896), (1280, 1280)]
	
	for det_size in det_sizes:
		logger.debug(f"Попытка детекции с размером {det_size}...")
		app = _get_face_analysis_with_size(det_size)
		faces = app.get(image, max_num=10)
		if faces:
			logger.info(f"Лицо найдено с размером детекции {det_size}")
			return faces
	
	# Если стандартные размеры не помогли, пробуем улучшения
	app = _get_face_analysis()  # Используем основной экземпляр с (1280, 1280)
	
	# Попытка 1: Оригинальное изображение с max_num=10 (увеличиваем лимит найденных лиц)
	faces = app.get(image, max_num=10)
	if faces:
		return faces
	
	# Попытка 2: Улучшение контраста с разными размерами детекции
	logger.debug("Попытка 2: улучшение контраста для детекции лиц...")
	lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
	l, a, b = cv2.split(lab)
	clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
	l = clahe.apply(l)
	enhanced = cv2.merge([l, a, b])
	enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
	
	# Пробуем улучшенное изображение с разными размерами детекции
	for det_size in det_sizes:
		app_size = _get_face_analysis_with_size(det_size)
		faces = app_size.get(enhanced, max_num=10)
		if faces:
			logger.info(f"Лицо найдено на улучшенном изображении с размером детекции {det_size}")
			return faces
	
	# Попытка 3: Повышение резкости с разными размерами детекции
	logger.debug("Попытка 3: повышение резкости для детекции лиц...")
	kernel = np.array([[-1, -1, -1],
	                   [-1,  9, -1],
	                   [-1, -1, -1]])
	sharpened = cv2.filter2D(image, -1, kernel * 0.2)
	
	# Пробуем заостренное изображение с разными размерами детекции
	for det_size in det_sizes:
		app_size = _get_face_analysis_with_size(det_size)
		faces = app_size.get(sharpened, max_num=10)
		if faces:
			logger.info(f"Лицо найдено на заостренном изображении с размером детекции {det_size}")
			return faces
	
	# Попытка 4: Масштабирование изображения (увеличиваем для лучшей детекции)
	logger.debug("Попытка 4: масштабирование изображения для детекции лиц...")
	if max_dim < 1024:
		scale = 1024 / max_dim
		new_w = int(w * scale)
		new_h = int(h * scale)
		scaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
		faces = app.get(scaled, max_num=10)
		if faces:
			return faces
	
	# Попытка 5: Уменьшение изображения (иногда большие изображения хуже детектируются)
	logger.debug("Попытка 5: уменьшение изображения для детекции лиц...")
	if max_dim > 1920:
		scale = 1920 / max_dim
		new_w = int(w * scale)
		new_h = int(h * scale)
		downscaled = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
		faces = app.get(downscaled, max_num=10)
		if faces:
			return faces
	
	# Попытка 6: Комбинация улучшения контраста и масштабирования
	logger.debug("Попытка 6: комбинация улучшения контраста и масштабирования...")
	if max_dim < 1024:
		scale = 1024 / max_dim
		new_w_enh = int(w * scale)
		new_h_enh = int(h * scale)
		scaled_enhanced = cv2.resize(enhanced, (new_w_enh, new_h_enh), interpolation=cv2.INTER_LINEAR)
		faces = app.get(scaled_enhanced, max_num=10)
		if faces:
			return faces
	
	# Попытка 7: Комбинация повышения резкости и улучшения контраста
	logger.debug("Попытка 7: комбинация повышения резкости и улучшения контраста...")
	sharpened_enhanced = cv2.addWeighted(enhanced, 0.7, sharpened, 0.3, 0)
	faces = app.get(sharpened_enhanced, max_num=10)
	if faces:
		return faces
	
	# Попытка 8: Нормализация яркости
	logger.debug("Попытка 8: нормализация яркости для детекции лиц...")
	# Конвертируем в YUV для работы с яркостью
	yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
	y, u, v = cv2.split(yuv)
	# Нормализуем канал яркости
	y_normalized = cv2.normalize(y, None, 0, 255, cv2.NORM_MINMAX)
	normalized = cv2.merge([y_normalized, u, v])
	normalized = cv2.cvtColor(normalized, cv2.COLOR_YUV2BGR)
	faces = app.get(normalized, max_num=10)
	if faces:
		return faces
	
	# Если все попытки не удались
	raise ValueError(
		"На изображении не обнаружено лиц. "
		"Пожалуйста, используйте фото с четко видимым лицом, хорошим освещением и прямым углом."
	)


def _get_gfpgan_model():
	"""
	Получает или загружает модель GFPGAN для восстановления качества лиц.
	
	Returns:
		Объект модели GFPGAN или None, если недоступен
	"""
	global _gfpgan_model
	if not GFPGAN_AVAILABLE:
		return None
	
	if _gfpgan_model is None:
		try:
			logger.info("Инициализация GFPGAN для улучшения качества лиц...")
			# GFPGAN автоматически скачает модель при первом использовании
			_gfpgan_model = GFPGANer(
				model_path='https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth',
				upscale=1,  # Не увеличиваем разрешение, только улучшаем качество
				arch='clean',
				channel_multiplier=2,
				bg_upsampler=None
			)
			logger.info("GFPGAN инициализирован")
		except Exception as exc:
			logger.warning("Не удалось инициализировать GFPGAN: %s. Будет использовано базовое улучшение.", exc)
			_gfpgan_model = None
	
	return _gfpgan_model


def _enhance_image_quality(image: np.ndarray) -> np.ndarray:
	"""
	Улучшает качество изображения: использует GFPGAN если доступен, иначе базовое улучшение.
	
	Args:
		image: Изображение в формате BGR (OpenCV)
	
	Returns:
		Улучшенное изображение
	"""
	# Пытаемся использовать GFPGAN для восстановления качества лица
	gfpgan = _get_gfpgan_model()
	if gfpgan is not None:
		try:
			logger.info("Применение GFPGAN для улучшения качества лица...")
			# GFPGAN ожидает RGB формат
			image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
			_, _, restored_img = gfpgan.enhance(image_rgb, has_aligned=False, only_center_face=False, paste_back=True)
			# Конвертируем обратно в BGR
			result = cv2.cvtColor(restored_img, cv2.COLOR_RGB2BGR)
			logger.info("GFPGAN успешно применён")
			return result
		except Exception as exc:
			logger.warning("Ошибка при применении GFPGAN: %s. Используется базовое улучшение.", exc)
	
	# Улучшенное улучшение качества через OpenCV с сохранением текстуры
	logger.info("Применение улучшенного улучшения качества с сохранением текстуры...")
	
	# Шаг 1: Проверка разрешения и upscaling для маленьких изображений
	h, w = image.shape[:2]
	max_dim = max(h, w)
	needs_upscale = max_dim < 1024
	original_size = (w, h)
	
	if needs_upscale:
		logger.debug(f"Upscaling изображения с {max_dim}px до 1024px для лучшего качества...")
		scale = 1024 / max_dim
		new_w = int(w * scale)
		new_h = int(h * scale)
		result = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
	else:
		result = image.copy()
	
	# Шаг 2: Легкое удаление шума только при необходимости (очень легкий median filter вместо bilateral)
	# Используем median filter только если изображение действительно шумное
	# Это сохраняет текстуру лучше, чем bilateral filter
	result = cv2.medianBlur(result, ksize=3)
	
	# Шаг 3: Улучшение контраста через CLAHE (более тонкие параметры для сохранения деталей)
	lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
	l, a, b = cv2.split(lab)
	# Используем более тонкие параметры CLAHE, чтобы не переусердствовать с контрастом
	clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
	l = clahe.apply(l)
	result = cv2.merge([l, a, b])
	result = cv2.cvtColor(result, cv2.COLOR_LAB2BGR)
	
	# Шаг 4: Тонкое повышение резкости через unsharp mask (сохраняет текстуру)
	# Используем более точный unsharp mask с меньшей интенсивностью
	gaussian = cv2.GaussianBlur(result, (0, 0), 1.0)
	sharpened = cv2.addWeighted(result, 1.5, gaussian, -0.5, 0)
	
	# Смешиваем с умеренным весом (75% оригинал, 25% заостренное) для сохранения текстуры
	result = cv2.addWeighted(result, 0.75, sharpened, 0.25, 0)
	
	# Шаг 5: Легкая коррекция яркости и насыщенности
	hsv = cv2.cvtColor(result, cv2.COLOR_BGR2HSV)
	h, s, v = cv2.split(hsv)
	# Увеличиваем насыщенность на 8% (меньше, чем было)
	s = cv2.add(s, int(255 * 0.08))
	s = np.clip(s, 0, 255).astype(np.uint8)
	# Легкое увеличение яркости на 3% (меньше, чем было)
	v = cv2.add(v, int(255 * 0.03))
	v = np.clip(v, 0, 255).astype(np.uint8)
	result = cv2.merge([h, s, v])
	result = cv2.cvtColor(result, cv2.COLOR_HSV2BGR)
	
	# Шаг 6: Возвращаем к исходному размеру, если было upscaling
	if needs_upscale:
		logger.debug(f"Возврат к исходному размеру {original_size}...")
		result = cv2.resize(result, original_size, interpolation=cv2.INTER_LANCZOS4)
	
	# НЕ используем финальный bilateral filter - он сглаживает текстуру
	# Вместо этого просто возвращаем результат
	
	return result


def _swap_face_using_inswapper(
	source_image: np.ndarray,
	target_face: object,
	source_face: object,
) -> np.ndarray:
	"""
	Заменяет лицо на исходном изображении используя модель inswapper.
	
	Args:
		source_image: Исходное изображение, где нужно заменить лицо
		target_face: Обнаруженное лицо на исходном изображении (которое нужно заменить)
		source_face: Обнаруженное лицо, которое нужно вставить
	
	Returns:
		Изображение с заменённым лицом
	"""
	model = _get_inswapper_model()
	
	try:
		# Используем API модели insightface для замены лица
		# model.get(frame, target_face, source_face, paste_back=True)
		# frame - изображение, где нужно заменить лицо
		# target_face - лицо на frame, которое нужно заменить
		# source_face - лицо, которое нужно вставить
		result_image = model.get(source_image, target_face, source_face, paste_back=True)
		return result_image
	except Exception as exc:
		logger.exception("Ошибка при замене лица: %s", exc)
		raise


async def swap_face(source_image_url: str, target_face_url: str) -> bytes:
	"""
	Выполняет замену лица на изображении.
	
	Args:
		source_image_url: URL изображения, где нужно заменить лицо
		target_face_url: URL изображения с лицом, которое нужно вставить
	
	Returns:
		bytes: Изображение с заменённым лицом в формате JPEG
	
	Raises:
		ValueError: Если на изображениях не обнаружено лиц или обнаружено несколько лиц
		Exception: При других ошибках обработки
	"""
	logger.info(f"Начало замены лица: source={source_image_url}, target={target_face_url}")
	
	# Загружаем изображения
	logger.info("Загрузка изображений...")
	source_image = await _download_image(source_image_url)
	target_image = await _download_image(target_face_url)
	logger.info(f"Изображения загружены: source shape={source_image.shape}, target shape={target_image.shape}")
	
	# Обнаруживаем лица
	logger.info("Обнаружение лиц на исходном изображении...")
	source_faces = _detect_faces(source_image)
	logger.info(f"Найдено лиц на исходном изображении: {len(source_faces)}")
	
	logger.info("Обнаружение лиц на целевом изображении...")
	target_faces = _detect_faces(target_image)
	logger.info(f"Найдено лиц на целевом изображении: {len(target_faces)}")
	
	if len(source_faces) > 1:
		raise ValueError(
			f"На исходном изображении обнаружено {len(source_faces)} лиц. "
			"Пожалуйста, используйте фото с одним лицом."
		)
	
	if len(target_faces) > 1:
		raise ValueError(
			f"На изображении с лицом обнаружено {len(target_faces)} лиц. "
			"Пожалуйста, используйте фото с одним лицом."
		)
	
	source_face = source_faces[0]
	target_face = target_faces[0]
	
	# Выполняем замену лица через inswapper
	# source_image - изображение, где нужно заменить лицо
	# source_face - лицо на source_image (которое нужно заменить)
	# target_face - лицо, которое нужно вставить (из второго фото)
	logger.info("Выполнение замены лица через inswapper...")
	result_image = _swap_face_using_inswapper(
		source_image, source_face, target_face
	)
	logger.info(f"Замена лица выполнена, результат shape={result_image.shape}")
	
	# Улучшаем качество изображения перед сохранением
	logger.info("Улучшение качества изображения...")
	result_image = _enhance_image_quality(result_image)
	
	# Конвертируем результат в JPEG bytes с максимальным качеством
	logger.info("Конвертация результата в JPEG...")
	_, buffer = cv2.imencode(".jpg", result_image, [cv2.IMWRITE_JPEG_QUALITY, 100])
	image_bytes = buffer.tobytes()
	logger.info(f"Замена лица завершена успешно, размер результата: {len(image_bytes)} bytes")
	return image_bytes

