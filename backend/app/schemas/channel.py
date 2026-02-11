from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ChannelCreate(BaseModel):
    tg_chat_id: int
    username: str | None = None
    title: str | None = None
    bot_admin_status: bool | None = None
    rights_snapshot: dict | None = None


class ChannelUpdate(BaseModel):
    username: str | None = None
    title: str | None = None
    bot_admin_status: bool | None = None
    rights_snapshot: dict | None = None


class ChannelManagerCreate(BaseModel):
    user_id: int | None = None
    tg_user_id: int | None = None
    tg_username: str | None = None
    permissions: dict | None = None


class ChannelManagerOut(BaseModel):
    id: int
    channel_id: int
    user_id: int
    tg_user_id: int
    tg_username: str | None
    permissions: dict | None = None


class TgAdminOut(BaseModel):
    tg_user_id: int
    tg_username: str | None
    first_name: str
    status: str


class ChannelOut(BaseModel):
    id: int
    tg_chat_id: int
    username: str | None
    title: str | None
    owner_user_id: int
    bot_admin_status: bool
    rights_snapshot: dict | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
