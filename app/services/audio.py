from app.config import get_settings
from app.utils.openai_client import create_openai_client
from openai import OpenAI
import aiofiles
import asyncio
import tempfile


settings = get_settings()
http_client = create_openai_client()
client = OpenAI(api_key=settings.openai_api_key, http_client=http_client)


async def speech_to_text(file_path: str) -> str:
	# Whisper STT через OpenAI
	with open(file_path, "rb") as f:
		res = client.audio.transcriptions.create(model="whisper-1", file=f)
		return res.text or ""


async def text_to_speech(text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
	"""
	Преобразует текст в речь через OpenAI TTS API.
	
	Args:
		text: Текст для озвучки
		voice: Голос (alloy, echo, fable, onyx, nova, shimmer)
		model: Модель TTS (tts-1 для стандартного качества, tts-1-hd для высокого)
	
	Returns:
		bytes: Аудиофайл в формате MP3
	"""
	response = client.audio.speech.create(
		model=model,
		voice=voice,
		input=text
	)
	
	# Читаем байты из response
	audio_bytes = b""
	for chunk in response.iter_bytes():
		audio_bytes += chunk
	
	return audio_bytes


