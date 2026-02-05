from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CreativeStatus


class CreativeCreate(BaseModel):
    actor_tg_user_id: int | None = None
    text: str | None = None
    media_file_ids: list[dict] | list[str] | None = None


class CreativeStatusUpdate(BaseModel):
    actor_tg_user_id: int | None = None
    status: CreativeStatus
    comment: str | None = None
    publish_at: datetime | None = None


class CreativeOut(BaseModel):
    id: int
    deal_id: int
    text: str | None
    media_file_ids: list[dict] | list[str] | None
    version: int
    status: CreativeStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
