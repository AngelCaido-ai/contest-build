from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EscrowPayment(Base):
    __tablename__ = "escrow_payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id"), unique=True, nullable=False)
    deposit_address: Mapped[str] = mapped_column(String, nullable=False)
    deposit_comment: Mapped[str | None] = mapped_column(String, nullable=True)
    deposit_key: Mapped[str | None] = mapped_column(String, nullable=True)
    expected_amount: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    tx_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    release_tx_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    refund_tx_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    payout_address: Mapped[str | None] = mapped_column(String, nullable=True)
    refund_address: Mapped[str | None] = mapped_column(String, nullable=True)
    released_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
