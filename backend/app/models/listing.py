from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    price_ton: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    price_usd: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    format: Mapped[str] = mapped_column(String, default="post", nullable=False)
    categories: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
