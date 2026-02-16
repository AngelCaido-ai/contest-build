from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    bot_token: str
    api_base_url: str = "http://localhost:8000"
    bot_secret: str
    redis_url: str = "redis://localhost:6379/1"
    miniapp_url: str = ""

    @field_validator("bot_token", "bot_secret", "api_base_url", "miniapp_url", mode="before")
    @classmethod
    def normalize_env(cls, v):
        if isinstance(v, str):
            value = v.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1].strip()
            return value
        return v

    model_config = SettingsConfigDict(extra="ignore")


settings = BotSettings()
