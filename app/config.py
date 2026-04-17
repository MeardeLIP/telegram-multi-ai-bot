from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from loguru import logger


class Settings(BaseSettings):
	model_config = SettingsConfigDict(env_file=(".env", "env.example"), env_file_encoding="utf-8", extra="ignore")

	bot_token: str = Field(default="")
	bot_username: str = Field(default="")
	openai_api_key: str = Field(default="")
	database_url: str = Field(default="postgresql+psycopg://app:app@db:5432/app")
	redis_url: str = Field(default="redis://redis:6379/0")
	yookassa_shop_id: str = Field(default="")
	yookassa_secret_key: str = Field(default="")
	telegram_payment_token: str = Field(default="")
	public_base_url: str = Field(default="http://localhost:8000")
	# ВНУТРЕННИЙ URL для обращения бота к API (обычно localhost/127.0.0.1 на том же сервере)
	api_internal_url: str = Field(default="http://localhost:8000")
	webhook_secret: str = Field(default="dev-webhook-secret")
	admin_ids: list[int] = Field(default_factory=list, alias="ADMIN_IDS")
	sentry_dsn: str = Field(default="")

	billing_vision_surcharge: int = Field(default=150)
	billing_stt_per_min: int = Field(default=900)
	billing_tts_per_1k_chars: int = Field(default=600)
	billing_faceswap_cost: int = Field(default=7500)
	billing_photo_enhance_cost: int = Field(default=4000)
	billing_photo_replace_bg_cost: int = Field(default=11000)
	billing_photo_remove_bg_cost: int = Field(default=7500)
	billing_photo_animate_cost: int = Field(default=10)  # Для теста 10 токенов
	billing_gpt_image_cost: int = Field(default=9500)
	log_level: str = Field(default="INFO")
	
	# Прокси для YooKassa (если нужен, на русском сервере не требуется)
	yookassa_proxy: str = Field(default="")
	# Прокси для OpenAI API (если нужен для работы с GPT)
	openai_proxy: str = Field(default="")
	
	# Настройки KLING-V2 API для оживления фото
	kling_access_key: str = Field(default="")
	kling_secret_key: str = Field(default="")
	kling_api_id: str = Field(default="")
	kling_api_base_url: str = Field(default="https://api-singapore.klingai.com/v1")  # Базовый URL для KLING API

	@field_validator("admin_ids", mode="before")
	def parse_admin_ids(cls, value: Any) -> list[int]:
		if value is None or value == "":
			return []
		if isinstance(value, (list, tuple, set)):
			return [int(v) for v in value]
		if isinstance(value, str):
			parts = [part.strip() for part in value.replace(",", " ").split() if part.strip()]
			return [int(part) for part in parts]
		return [int(value)]
	
	@model_validator(mode="after")
	def validate_kling_settings(self):
		"""Проверяет и логирует загрузку KLING API настроек при инициализации."""
		# Проверяем KLING_ACCESS_KEY
		access_key = (self.kling_access_key or "").strip()
		if access_key:
			token_length = len(access_key)
			token_preview = f"{access_key[:4]}...{access_key[-4:]}" if token_length > 8 else "***"
			logger.info(
				f"✅ KLING_ACCESS_KEY загружен: длина={token_length}, превью={token_preview}, "
				f"base_url={self.kling_api_base_url}"
			)
		else:
			logger.warning("⚠️ KLING_ACCESS_KEY не установлен или пустой в переменных окружения")
		
		# Проверяем другие KLING переменные (без вывода значений)
		if self.kling_secret_key:
			logger.debug(f"KLING_SECRET_KEY загружен: длина={len(self.kling_secret_key.strip())}")
		if self.kling_api_id:
			logger.debug(f"KLING_API_ID загружен: {self.kling_api_id[:10]}...")
		
		return self


def get_settings() -> Settings:
	return Settings()  # type: ignore[call-arg]


