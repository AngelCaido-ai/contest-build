"""Make all DateTime columns timezone-aware (TIMESTAMP WITH TIME ZONE).

Existing naive timestamps are treated as UTC and preserved as-is;
the DB will attach +00:00 to them automatically on column type change.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_datetime_timezone_aware"
down_revision = "0007_extended_channel_stats"
branch_labels = None
depends_on = None

_TZ = sa.DateTime(timezone=True)
_NO_TZ = sa.DateTime()

_COLUMNS: list[tuple[str, str, bool]] = [
    # (table, column, nullable)
    ("users", "created_at", False),
    ("channels", "created_at", False),
    ("channel_stats", "updated_at", False),
    ("listings", "created_at", False),
    ("requests", "created_at", False),
    ("deals", "publish_at", True),
    ("deals", "posted_at", True),
    ("deals", "verification_started_at", True),
    ("deals", "created_at", False),
    ("deals", "updated_at", False),
    ("escrow_payments", "confirmed_at", True),
    ("escrow_payments", "released_at", True),
    ("escrow_payments", "refunded_at", True),
    ("escrow_payments", "swept_at", True),
    ("escrow_payments", "created_at", False),
    ("creatives", "created_at", False),
    ("deal_events", "created_at", False),
]


def upgrade() -> None:
    for table, column, nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                type_=_TZ,
                existing_type=_NO_TZ,
                existing_nullable=nullable,
            )


def downgrade() -> None:
    for table, column, nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                type_=_NO_TZ,
                existing_type=_TZ,
                existing_nullable=nullable,
            )
