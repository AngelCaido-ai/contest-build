from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DealEventCreate(BaseModel):
    type: str
    payload: dict | None = None


class DealEventOut(BaseModel):
    id: int
    deal_id: int
    type: str
    payload: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
