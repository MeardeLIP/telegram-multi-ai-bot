from typing import Sequence
from openai import OpenAI
from app.config import get_settings
from app.utils.openai_client import create_openai_client


settings = get_settings()
http_client = create_openai_client()
client = OpenAI(api_key=settings.openai_api_key, http_client=http_client)


async def chat_completion(messages: Sequence[dict], model: str = "gpt-5-mini") -> str:
	# Простая обёртка для текстового ответа
	resp = client.chat.completions.create(model=model, messages=list(messages))
	return resp.choices[0].message.content or ""


async def vision_analyze(image_url: str, prompt: str = "Опиши, что на изображении") -> str:
	messages = [
		{
			"role": "user",
			"content": [
				{"type": "text", "text": prompt},
				{"type": "image_url", "image_url": {"url": image_url}},
			],
		}
	]
	resp = client.chat.completions.create(model="gpt-5-mini", messages=messages)  # предполагаем мультимодальность
	return resp.choices[0].message.content or ""

