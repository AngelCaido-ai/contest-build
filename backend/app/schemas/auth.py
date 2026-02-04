from pydantic import BaseModel, ConfigDict

from app.schemas.user import UserOut


class AuthRequest(BaseModel):
    init_data: str
    roles: list[str] | None = None


class BotAuthRequest(BaseModel):
    tg_user_id: int
    roles: list[str] | None = None


class AuthResponse(BaseModel):
    token: str
    user: UserOut

    model_config = ConfigDict(from_attributes=True)
