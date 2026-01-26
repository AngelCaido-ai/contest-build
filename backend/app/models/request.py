from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    budget: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    niche: Mapped[str | None] = mapped_column(String, nullable=True)
    languages: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    min_subs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dates: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
