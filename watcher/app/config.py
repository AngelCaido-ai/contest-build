from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class WatcherSettings(BaseSettings):
    telethon_api_id: int
    telethon_api_hash: str
    telethon_session: str
    api_base_url: str = "http://localhost:8000"
    bot_secret: str

    @field_validator(
        "telethon_api_hash", "telethon_session", "bot_secret", "api_base_url",
        mode="before",
    )
    @classmethod
    def normalize_env(cls, v):
        if isinstance(v, str):
            value = v.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1].strip()
            return value
        return v

    model_config = SettingsConfigDict(extra="ignore")


settings = WatcherSettings()
