from alembic import op
import sqlalchemy as sa

revision = "0006_sweep_fields"
down_revision = "0005_user_tg_username"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrow_payments", sa.Column("sweep_tx_hash", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("swept_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("escrow_payments", "swept_at")
    op.drop_column("escrow_payments", "sweep_tx_hash")
