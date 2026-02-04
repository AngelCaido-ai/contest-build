from alembic import op
import sqlalchemy as sa

revision = "0004_deal_brief"
down_revision = "0003_escrow_comment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("deals", sa.Column("brief", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("deals", "brief")
