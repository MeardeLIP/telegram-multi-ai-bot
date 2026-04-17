"""add promocode usage tracking

Revision ID: 0005_add_promocode_usage
Revises: 0004_tg_payment_charge_id
Create Date: 2025-11-17 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0005_add_promocode_usage'
down_revision: Union[str, None] = '0004_tg_payment_charge_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.create_table(
		'promocode_usage',
		sa.Column('id', sa.Integer(), nullable=False),
		sa.Column('user_id', sa.Integer(), nullable=False),
		sa.Column('promo_code', sa.String(length=64), nullable=False),
		sa.Column('used_at', sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(['promo_code'], ['promocodes.code'], ),
		sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
		sa.PrimaryKeyConstraint('id'),
		sa.UniqueConstraint('user_id', 'promo_code', name='uq_user_promo')
	)
	op.create_index(op.f('ix_promocode_usage_user_id'), 'promocode_usage', ['user_id'], unique=False)
	op.create_index(op.f('ix_promocode_usage_promo_code'), 'promocode_usage', ['promo_code'], unique=False)


def downgrade() -> None:
	op.drop_index(op.f('ix_promocode_usage_promo_code'), table_name='promocode_usage')
	op.drop_index(op.f('ix_promocode_usage_user_id'), table_name='promocode_usage')
	op.drop_table('promocode_usage')

