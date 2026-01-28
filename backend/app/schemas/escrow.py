from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EscrowDepositRequest(BaseModel):
    expected_amount: float | None = None


class EscrowConfirmRequest(BaseModel):
    tx_hash: str


class EscrowReleaseRequest(BaseModel):
    payout_address: str | None = None


class EscrowRefundRequest(BaseModel):
    refund_address: str | None = None
    reason: str | None = None


class EscrowOut(BaseModel):
    id: int
    deal_id: int
    deposit_address: str
    deposit_comment: str | None
    expected_amount: float | None
    tx_hash: str | None
    confirmed_at: datetime | None
    release_tx_hash: str | None
    refund_tx_hash: str | None
    payout_address: str | None
    refund_address: str | None
    released_at: datetime | None
    refunded_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
