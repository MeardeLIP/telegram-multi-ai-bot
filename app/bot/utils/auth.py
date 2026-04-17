from functools import lru_cache

from app.config import get_settings


@lru_cache(maxsize=1)
def _admin_ids_cache() -> tuple[int, ...]:
	settings = get_settings()
	return tuple(settings.admin_ids)


def is_admin(tg_id: int) -> bool:
	return tg_id in _admin_ids_cache()

