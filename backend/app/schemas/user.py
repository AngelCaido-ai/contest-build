from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.utils.ton_address import validate_ton_address


class UserOut(BaseModel):
    id: int
    tg_user_id: int
    tg_username: str | None
    roles: list[str]
    linked_wallet: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserWalletUpdate(BaseModel):
    actor_tg_user_id: int | None = None
    linked_wallet: str | None = None

    @field_validator("linked_wallet")
    @classmethod
    def validate_linked_wallet(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_ton_address(value)


class UserWalletSet(BaseModel):
    linked_wallet: str | None = None
