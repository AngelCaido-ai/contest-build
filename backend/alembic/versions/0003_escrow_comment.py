from alembic import op
import sqlalchemy as sa

revision = "0003_escrow_comment"
down_revision = "0002_escrow_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrow_payments", sa.Column("deposit_comment", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("escrow_payments", "deposit_comment")
