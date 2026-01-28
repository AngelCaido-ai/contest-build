from alembic import op
import sqlalchemy as sa

revision = "0002_escrow_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrow_payments", sa.Column("deposit_key", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("release_tx_hash", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("refund_tx_hash", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("payout_address", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("refund_address", sa.String(), nullable=True))
    op.add_column("escrow_payments", sa.Column("released_at", sa.DateTime(), nullable=True))
    op.add_column("escrow_payments", sa.Column("refunded_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("escrow_payments", "refunded_at")
    op.drop_column("escrow_payments", "released_at")
    op.drop_column("escrow_payments", "refund_address")
    op.drop_column("escrow_payments", "payout_address")
    op.drop_column("escrow_payments", "refund_tx_hash")
    op.drop_column("escrow_payments", "release_tx_hash")
    op.drop_column("escrow_payments", "deposit_key")
