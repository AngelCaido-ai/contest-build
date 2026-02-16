from alembic import op
import sqlalchemy as sa

revision = "0007_extended_channel_stats"
down_revision = "0006_sweep_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("channel_stats", sa.Column("shares_per_post", sa.Float(), nullable=True))
    op.add_column("channel_stats", sa.Column("reactions_per_post", sa.Float(), nullable=True))
    op.add_column("channel_stats", sa.Column("enabled_notifications", sa.Float(), nullable=True))
    op.add_column("channel_stats", sa.Column("subscribers_prev", sa.Integer(), nullable=True))
    op.add_column("channel_stats", sa.Column("views_per_post_prev", sa.Float(), nullable=True))
    op.add_column("channel_stats", sa.Column("shares_per_post_prev", sa.Float(), nullable=True))
    op.add_column("channel_stats", sa.Column("reactions_per_post_prev", sa.Float(), nullable=True))

    # views_per_post was Integer, now Float to preserve fractional averages
    with op.batch_alter_table("channel_stats") as batch_op:
        batch_op.alter_column("views_per_post", type_=sa.Float(), existing_type=sa.Integer(), existing_nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("channel_stats") as batch_op:
        batch_op.alter_column("views_per_post", type_=sa.Integer(), existing_type=sa.Float(), existing_nullable=True)

    op.drop_column("channel_stats", "reactions_per_post_prev")
    op.drop_column("channel_stats", "shares_per_post_prev")
    op.drop_column("channel_stats", "views_per_post_prev")
    op.drop_column("channel_stats", "subscribers_prev")
    op.drop_column("channel_stats", "enabled_notifications")
    op.drop_column("channel_stats", "reactions_per_post")
    op.drop_column("channel_stats", "shares_per_post")
