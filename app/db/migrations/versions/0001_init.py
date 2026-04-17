from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
	op.create_table(
		"users",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("tg_id", sa.BigInteger(), nullable=False, unique=True, index=True),
		sa.Column("username", sa.String(length=255), nullable=True),
		sa.Column("ref_code", sa.String(length=32), nullable=True),
		sa.Column("invited_by", sa.Integer(), nullable=True),
		sa.Column("role", sa.String(length=32), nullable=False, server_default="user"),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.UniqueConstraint("ref_code"),
	)

	op.create_table(
		"balances",
		sa.Column("user_id", sa.Integer(), primary_key=True),
		sa.Column("tokens", sa.BigInteger(), nullable=False, server_default="0"),
		sa.Column("subscription_tier", sa.String(length=32), nullable=True),
		sa.Column("expires_at", sa.DateTime(), nullable=True),
		sa.Column("auto_renew", sa.Boolean(), nullable=False, server_default=sa.text("false")),
		sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
	)

	op.create_table(
		"usage",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("user_id", sa.Integer(), nullable=False, index=True),
		sa.Column("tokens_used", sa.Integer(), nullable=False),
		sa.Column("model", sa.String(length=64), nullable=False),
		sa.Column("mode", sa.String(length=32), nullable=False),
		sa.Column("created_at", sa.DateTime(), nullable=False),
	)

	op.create_table(
		"payments",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("user_id", sa.Integer(), nullable=False),
		sa.Column("plan_code", sa.String(length=32), nullable=False),
		sa.Column("amount_rub", sa.Integer(), nullable=False),
		sa.Column("status", sa.String(length=32), nullable=False),
		sa.Column("provider", sa.String(length=32), nullable=False),
		sa.Column("provider_id", sa.String(length=128), nullable=True),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
	)

	op.create_table(
		"promocodes",
		sa.Column("code", sa.String(length=64), primary_key=True),
		sa.Column("tokens_bonus", sa.Integer(), nullable=False, server_default="0"),
		sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
		sa.Column("used_count", sa.Integer(), nullable=False, server_default="0"),
		sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("expires_at", sa.DateTime(), nullable=True),
	)

	op.create_table(
		"referrals",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("user_id", sa.Integer(), nullable=False),
		sa.Column("invited_user_id", sa.Integer(), nullable=False),
		sa.Column("reward_tokens", sa.Integer(), nullable=False, server_default="1000"),
		sa.Column("rewarded_at", sa.DateTime(), nullable=True),
		sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
	)

	op.create_table(
		"dialogs",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("user_id", sa.Integer(), nullable=False),
		sa.Column("title", sa.String(length=255), nullable=True),
		sa.Column("model", sa.String(length=64), nullable=False, server_default="gpt-5"),
		sa.Column("system_prompt", sa.Text(), nullable=True),
		sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
	)

	op.create_table(
		"messages",
		sa.Column("id", sa.Integer(), primary_key=True),
		sa.Column("dialog_id", sa.Integer(), nullable=False),
		sa.Column("role", sa.String(length=16), nullable=False),
		sa.Column("content", sa.Text(), nullable=False),
		sa.Column("tokens_in", sa.Integer(), nullable=True),
		sa.Column("tokens_out", sa.Integer(), nullable=True),
		sa.Column("meta", sa.JSON(), nullable=True),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(["dialog_id"], ["dialogs.id"]),
	)


def downgrade() -> None:
	op.drop_table("messages")
	op.drop_table("dialogs")
	op.drop_table("referrals")
	op.drop_table("promocodes")
	op.drop_table("payments")
	op.drop_table("usage")
	op.drop_table("balances")
	op.drop_table("users")


