from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Balance, Payment, User


async def get_profile(session: AsyncSession, user_id: int) -> dict:
	user = await session.scalar(select(User).where(User.id == user_id))
	bal = await session.scalar(select(Balance).where(Balance.user_id == user_id))
	return {
		"user": {"id": user.id if user else None},
		"balance": {
			"tokens": bal.tokens if bal else 0,
			"tier": bal.subscription_tier if bal else None,
			"expires_at": bal.expires_at.isoformat() if bal and bal.expires_at else None,
		},
	}


