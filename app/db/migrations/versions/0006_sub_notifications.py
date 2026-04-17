"""add subscription notifications tracking

Revision ID: 0006_sub_notifications
Revises: 0005_add_promocode_usage
Create Date: 2025-01-17 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0006_sub_notifications"
down_revision = "0005_add_promocode_usage"
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"subscription_notifications",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("user_id", sa.Integer(), nullable=False),
		sa.Column("notification_type", sa.String(length=16), nullable=False),
		sa.Column("sent_at", sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
		sa.UniqueConstraint("user_id", "notification_type", name="uq_user_notification_type"),
	)
	op.create_index("ix_subscription_notifications_user_id", "subscription_notifications", ["user_id"])
	op.create_index("ix_subscription_notifications_sent_at", "subscription_notifications", ["sent_at"])


def downgrade() -> None:
	op.drop_index("ix_subscription_notifications_sent_at", table_name="subscription_notifications")
	op.drop_index("ix_subscription_notifications_user_id", table_name="subscription_notifications")
	op.drop_table("subscription_notifications")

