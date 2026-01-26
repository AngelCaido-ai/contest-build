from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ChannelStats(Base):
    __tablename__ = "channel_stats"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), unique=True, nullable=False)
    subscribers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_per_post: Mapped[int | None] = mapped_column(Integer, nullable=True)
    languages_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    premium_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
