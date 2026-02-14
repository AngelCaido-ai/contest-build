from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "contest"
    database_url: str = "postgresql+psycopg2://contest:contest@localhost:5432/contest"
    redis_url: str = "redis://localhost:6379/0"
    bot_token: str = ""
    bot_secret: str
    jwt_secret: str
    jwt_ttl_minutes: int = 1440
    telethon_api_id: int | None = None
    telethon_api_hash: str | None = None
    telethon_session: str | None = None
    ton_hot_wallet: str | None = None
    ton_api_key: str | None = None
    ton_network: str = "mainnet"
    ton_api_url: str = "https://toncenter.com/api/v2"
    ton_api_timeout_seconds: int = 10
    ton_wallet_id: int | None = None
    ton_wallet_subwallet: int | None = None
    ton_wallet_version: str | None = None
    ton_reserve_ton: float = 0.02
    ton_deposit_comment_prefix: str = "deal"
    escrow_secret_key: str | None = None
    cors_origins: str = ""
    bot_log_chat_id: int | None = None
    payment_timeout_minutes: int = 1440
    verification_window_minutes: int = 60
    sweep_delay_minutes: int = 5
    sweep_min_balance_ton: float = 0.005
    rate_limit_escrow_deposit: str = "10/minute"
    rate_limit_escrow_bot: str = "20/minute"
    init_data_max_age_seconds: int = 300

    @field_validator("telethon_api_id", "bot_log_chat_id", "ton_wallet_id", "ton_wallet_subwallet", mode="before")
    @classmethod
    def parse_int_or_none(cls, v):
        if v == "" or v is None:
            return None
        return int(v) if isinstance(v, str) else v

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
