from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_usage_success"
down_revision = "0001_init"
branch_labels = None
depends_on = None


def upgrade() -> None:
	# Добавляем поле success с дефолтным значением True для существующих записей
	op.add_column("usage", sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.text("true")))
	# Добавляем поле error_message, которое может быть NULL
	op.add_column("usage", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
	# Удаляем поля при откате миграции
	op.drop_column("usage", "error_message")
	op.drop_column("usage", "success")

