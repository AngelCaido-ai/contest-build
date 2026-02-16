from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import CreativeStatus

TZDateTime = DateTime(timezone=True)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Creative(Base):
    __tablename__ = "creatives"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    media_file_ids: Mapped[list[dict] | list[str] | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[CreativeStatus] = mapped_column(Enum(CreativeStatus), default=CreativeStatus.DRAFT, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime, default=_utcnow)
