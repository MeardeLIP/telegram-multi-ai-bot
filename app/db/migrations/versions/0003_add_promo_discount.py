"""add promo discount percent

Revision ID: 0003_add_promo_discount
Revises: 0002_add_usage_success
Create Date: 2025-11-15 02:19:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_add_promo_discount'
down_revision: Union[str, None] = '0002_add_usage_success'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	op.add_column('promocodes', sa.Column('discount_percent', sa.Integer(), nullable=False, server_default=sa.text('0')))
	op.add_column('promocodes', sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')))


def downgrade() -> None:
	op.drop_column('promocodes', 'created_at')
	op.drop_column('promocodes', 'discount_percent')

