"""add tg payment charge id

Revision ID: 0004_tg_payment_charge_id
Revises: 0003_add_promo_discount
Create Date: 2025-11-17 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0004_tg_payment_charge_id'
down_revision: Union[str, None] = '0003_add_promo_discount'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	# Эта миграция уже была применена в БД, но файл был удален
	# Оставляем пустую функцию, чтобы Alembic мог построить цепочку миграций
	pass


def downgrade() -> None:
	# Эта миграция уже была применена в БД, но файл был удален
	# Оставляем пустую функцию, чтобы Alembic мог построить цепочку миграций
	pass

