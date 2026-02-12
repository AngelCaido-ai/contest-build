from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.ton_address import validate_ton_address


class EscrowDepositRequest(BaseModel):
    expected_amount: float | None = None


class EscrowConfirmRequest(BaseModel):
    tx_hash: str


class EscrowReleaseRequest(BaseModel):
    payout_address: str | None = None

    @field_validator("payout_address")
    @classmethod
    def validate_payout_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_ton_address(value)


class EscrowRefundRequest(BaseModel):
    refund_address: str | None = None
    reason: str | None = None

    @field_validator("refund_address")
    @classmethod
    def validate_refund_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_ton_address(value)


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
