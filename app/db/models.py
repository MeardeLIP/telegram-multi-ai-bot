from sqlalchemy import String, Integer, BigInteger, Boolean, ForeignKey, DateTime, Text, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from .session import Base


class User(Base):
	__tablename__ = "users"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
	username: Mapped[str | None] = mapped_column(String(255), nullable=True)
	ref_code: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)
	invited_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
	role: Mapped[str] = mapped_column(String(32), default="user")
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

	balance: Mapped["Balance"] = relationship(back_populates="user", uselist=False)


class Balance(Base):
	__tablename__ = "balances"

	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), primary_key=True)
	tokens: Mapped[int] = mapped_column(BigInteger, default=0)
	subscription_tier: Mapped[str | None] = mapped_column(String(32), nullable=True)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
	auto_renew: Mapped[bool] = mapped_column(Boolean, default=False)

	user: Mapped[User] = relationship(back_populates="balance")


class Usage(Base):
	__tablename__ = "usage"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	tokens_used: Mapped[int] = mapped_column(Integer)
	model: Mapped[str] = mapped_column(String(64))
	mode: Mapped[str] = mapped_column(String(32))
	success: Mapped[bool] = mapped_column(Boolean, default=True)
	error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Payment(Base):
	__tablename__ = "payments"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	plan_code: Mapped[str] = mapped_column(String(32))
	amount_rub: Mapped[int] = mapped_column(Integer)
	status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
	provider: Mapped[str] = mapped_column(String(32), default="yookassa")
	provider_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCode(Base):
	__tablename__ = "promocodes"

	code: Mapped[str] = mapped_column(String(64), primary_key=True)
	tokens_bonus: Mapped[int] = mapped_column(Integer, default=0)
	discount_percent: Mapped[int] = mapped_column(Integer, default=0)  # Процент скидки (0-100)
	max_uses: Mapped[int] = mapped_column(Integer, default=1)
	used_count: Mapped[int] = mapped_column(Integer, default=0)
	active: Mapped[bool] = mapped_column(Boolean, default=True)
	expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
	valid_days: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Количество дней действия промокода
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PromoCodeUsage(Base):
	__tablename__ = "promocode_usage"
	__table_args__ = (
		UniqueConstraint('user_id', 'promo_code', name='uq_user_promo'),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	promo_code: Mapped[str] = mapped_column(ForeignKey("promocodes.code"), index=True)
	used_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Referral(Base):
	__tablename__ = "referrals"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	invited_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	reward_tokens: Mapped[int] = mapped_column(Integer, default=1000)
	rewarded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Dialog(Base):
	__tablename__ = "dialogs"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	title: Mapped[str | None] = mapped_column(String(255), nullable=True)
	model: Mapped[str] = mapped_column(String(64), default="gpt-5")
	system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
	is_active: Mapped[bool] = mapped_column(Boolean, default=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Message(Base):
	__tablename__ = "messages"

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	dialog_id: Mapped[int] = mapped_column(ForeignKey("dialogs.id"), index=True)
	role: Mapped[str] = mapped_column(String(16))
	content: Mapped[str] = mapped_column(Text)
	tokens_in: Mapped[int | None] = mapped_column(Integer, nullable=True)
	tokens_out: Mapped[int | None] = mapped_column(Integer, nullable=True)
	meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
	created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class SubscriptionNotification(Base):
	__tablename__ = "subscription_notifications"
	__table_args__ = (
		UniqueConstraint('user_id', 'notification_type', name='uq_user_notification_type'),
	)

	id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
	user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
	notification_type: Mapped[str] = mapped_column(String(16))  # "7_days" или "3_days"
	sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


