from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CreativeStatus


class CreativeCreate(BaseModel):
    text: str | None = None
    media_file_ids: list[str] | None = None


class CreativeStatusUpdate(BaseModel):
    status: CreativeStatus


class CreativeOut(BaseModel):
    id: int
    deal_id: int
    text: str | None
    media_file_ids: list[str] | None
    version: int
    status: CreativeStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
