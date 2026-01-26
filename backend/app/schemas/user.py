from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    id: int
    tg_user_id: int
    roles: list[str]
    linked_wallet: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
