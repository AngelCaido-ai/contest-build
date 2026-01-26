from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    deal_status = sa.Enum(
        "NEGOTIATING",
        "TERMS_LOCKED",
        "AWAITING_PAYMENT",
        "FUNDED",
        "CREATIVE_DRAFT",
        "CREATIVE_REVIEW",
        "APPROVED",
        "SCHEDULED",
        "POSTED",
        "VERIFYING",
        "RELEASED",
        "REFUNDED",
        "CANCELED",
        name="dealstatus",
    )
    creative_status = sa.Enum("DRAFT", "REVIEW", "APPROVED", name="creativestatus")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_user_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("roles", sa.JSON, nullable=False),
        sa.Column("linked_wallet", sa.String, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("tg_chat_id", sa.BigInteger, nullable=False, unique=True),
        sa.Column("username", sa.String, nullable=True),
        sa.Column("title", sa.String, nullable=True),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("bot_admin_status", sa.Boolean, nullable=False),
        sa.Column("rights_snapshot", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "channel_managers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permissions", sa.JSON, nullable=True),
    )

    op.create_table(
        "channel_stats",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False, unique=True),
        sa.Column("subscribers", sa.Integer, nullable=True),
        sa.Column("views_per_post", sa.Integer, nullable=True),
        sa.Column("languages_json", sa.JSON, nullable=True),
        sa.Column("premium_json", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("source", sa.String, nullable=True),
    )

    op.create_table(
        "listings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("price_ton", sa.Numeric(18, 8), nullable=True),
        sa.Column("price_usd", sa.Numeric(18, 2), nullable=True),
        sa.Column("format", sa.String, nullable=False),
        sa.Column("categories", sa.JSON, nullable=True),
        sa.Column("constraints", sa.JSON, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("advertiser_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("budget", sa.Numeric(18, 2), nullable=True),
        sa.Column("niche", sa.String, nullable=True),
        sa.Column("languages", sa.JSON, nullable=True),
        sa.Column("min_subs", sa.Integer, nullable=True),
        sa.Column("min_views", sa.Integer, nullable=True),
        sa.Column("dates", sa.JSON, nullable=True),
        sa.Column("brief", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("listing_id", sa.Integer, sa.ForeignKey("listings.id"), nullable=True),
        sa.Column("request_id", sa.Integer, sa.ForeignKey("requests.id"), nullable=True),
        sa.Column("advertiser_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id"), nullable=False),
        sa.Column("price", sa.Numeric(18, 2), nullable=True),
        sa.Column("format", sa.String, nullable=True),
        sa.Column("publish_at", sa.DateTime, nullable=True),
        sa.Column("verification_window", sa.Integer, nullable=True),
        sa.Column("status", deal_status, nullable=False),
        sa.Column("posted_message_id", sa.BigInteger, nullable=True),
        sa.Column("posted_at", sa.DateTime, nullable=True),
        sa.Column("verification_started_at", sa.DateTime, nullable=True),
        sa.Column("tampered", sa.Boolean, nullable=False),
        sa.Column("deleted", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "escrow_payments",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.Integer, sa.ForeignKey("deals.id"), nullable=False, unique=True),
        sa.Column("deposit_address", sa.String, nullable=False),
        sa.Column("expected_amount", sa.Numeric(18, 8), nullable=True),
        sa.Column("tx_hash", sa.String, nullable=True),
        sa.Column("confirmed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "creatives",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.Integer, sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        sa.Column("media_file_ids", sa.JSON, nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", creative_status, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "deal_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("deal_id", sa.Integer, sa.ForeignKey("deals.id"), nullable=False),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("deal_events")
    op.drop_table("creatives")
    op.drop_table("escrow_payments")
    op.drop_table("deals")
    op.drop_table("requests")
    op.drop_table("listings")
    op.drop_table("channel_stats")
    op.drop_table("channel_managers")
    op.drop_table("channels")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS dealstatus")
    op.execute("DROP TYPE IF EXISTS creativestatus")
