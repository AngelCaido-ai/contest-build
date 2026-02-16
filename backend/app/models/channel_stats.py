from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TZDateTime = DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChannelStats(Base):
    __tablename__ = "channel_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), unique=True, nullable=False)
    subscribers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    reactions_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled_notifications: Mapped[float | None] = mapped_column(Float, nullable=True)

    subscribers_prev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    reactions_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)

    languages_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    premium_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
