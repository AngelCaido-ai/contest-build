from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EscrowDepositRequest(BaseModel):
    expected_amount: float | None = None


class EscrowConfirmRequest(BaseModel):
    tx_hash: str


class EscrowOut(BaseModel):
    id: int
    deal_id: int
    deposit_address: str
    expected_amount: float | None
    tx_hash: str | None
    confirmed_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
