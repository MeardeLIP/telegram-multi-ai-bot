"""add valid_days to promocodes

Revision ID: 0007_promo_valid_days
Revises: 0006_sub_notifications
Create Date: 2025-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0007_promo_valid_days"
down_revision = "0006_sub_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.add_column("promocodes", sa.Column("valid_days", sa.Integer(), nullable=True))


def downgrade() -> None:
	op.drop_column("promocodes", "valid_days")

