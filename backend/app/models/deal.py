from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DealStatus


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id"), nullable=True)
    request_id: Mapped[int | None] = mapped_column(ForeignKey("requests.id"), nullable=True)
    advertiser_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"), nullable=False)
    price: Mapped[float | None] = mapped_column(Numeric(18, 2), nullable=True)
    format: Mapped[str | None] = mapped_column(String, nullable=True)
    brief: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[DealStatus] = mapped_column(Enum(DealStatus), default=DealStatus.NEGOTIATING, nullable=False)
    posted_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verification_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tampered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
