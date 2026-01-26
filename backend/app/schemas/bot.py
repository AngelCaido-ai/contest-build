from pydantic import BaseModel


class TamperRequest(BaseModel):
    channel_tg_chat_id: int
    message_id: int


class BotChannelCreate(BaseModel):
    owner_tg_user_id: int
    tg_chat_id: int
    username: str | None = None
    title: str | None = None
    bot_admin_status: bool | None = None
    rights_snapshot: dict | None = None
