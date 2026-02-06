from alembic import op
import sqlalchemy as sa

revision = "0005_user_tg_username"
down_revision = "0004_deal_brief"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("tg_username", sa.String(), nullable=True))
    op.create_unique_constraint("uq_users_tg_username", "users", ["tg_username"])


def downgrade() -> None:
    op.drop_constraint("uq_users_tg_username", "users", type_="unique")
    op.drop_column("users", "tg_username")
