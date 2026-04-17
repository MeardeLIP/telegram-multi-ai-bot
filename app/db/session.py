from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
import sys
import asyncio

# Исправление для Windows: используем WindowsSelectorEventLoopPolicy вместо ProactorEventLoop
# Это необходимо для работы psycopg (async PostgreSQL драйвер) на Windows
# Должно быть установлено ДО создания async engine
if sys.platform == "win32":
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.config import get_settings


class Base(DeclarativeBase):
	pass


settings = get_settings()

# Use async PG URL
async_engine = create_async_engine(
	settings.database_url.replace("postgresql+psycopg", "postgresql+psycopg_async"),
	echo=False,
	pool_pre_ping=True,
)

async_session_maker = async_sessionmaker(bind=async_engine, class_=AsyncSession, expire_on_commit=False)


