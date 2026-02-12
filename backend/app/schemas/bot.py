from datetime import datetime

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


class BotUserUpsert(BaseModel):
    tg_user_id: int
    tg_username: str | None = None


class BotListingCreate(BaseModel):
    owner_tg_user_id: int
    channel_id: int
    price_ton: float | None = None
    price_usd: float | None = None
    format: str | None = "post"
    categories: list[str] | None = None
    constraints: dict | None = None
    active: bool | None = True


class BotRequestCreate(BaseModel):
    advertiser_tg_user_id: int
    budget: float | None = None
    niche: str | None = None
    languages: list[str] | None = None
    min_subs: int | None = None
    min_views: int | None = None
    dates: dict | None = None
    brief: str | None = None


class BotDealCreate(BaseModel):
    owner_tg_user_id: int
    listing_id: int | None = None
    request_id: int | None = None
    channel_id: int | None = None
    price: float | None = None
    format: str | None = None
    brief: str | None = None
    publish_at: datetime | None = None
    verification_window: int | None = None


class BotEscrowDepositRequest(BaseModel):
    actor_tg_user_id: int
    expected_amount: float | None = None


class BotAdvertiserBrief(BaseModel):
    actor_tg_user_id: int
    text: str | None = None
    publish_at: datetime | None = None
    media_file_ids: list[dict] | None = None


class BotDealMessageCreate(BaseModel):
    actor_tg_user_id: int
    text: str | None = None
    media_file_ids: list[dict] | None = None
    reply_to_event_id: int | None = None
