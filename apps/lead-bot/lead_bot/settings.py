from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    core_api_url: str = "http://core-api:8000"
    api_key_bot: str = ""
    telegram_bot_token: str = ""
    buffer_db_path: str = "/tmp/lead_bot_buffer.sqlite3"
    flush_interval_seconds: int = 60

    # Public site URL used in the /start platform map (one card link).
    public_site_url: str = "https://ai-verdict.ru"
    # Contract AI System URL (external surface, separate Docker on host).
    contract_ai_url: str = "https://contract.ai-verdict.ru"
    # Telegram channel username (without leading @) for the news entry point.
    public_channel_username: str = "ai_verdict"
    # Reader-bot username (without leading @).
    public_reader_bot_username: str = "legal_ai_news_reader_bot"
    # This bot's own username (without leading @) — used to assemble Mini App
    # deep-links of the form t.me/<this_bot>/<app_name>?startapp=... .
    public_self_bot_username: str = "legal_ai_helper_new_bot"
    # Name of the Mini App registered against this bot in @BotFather.
    public_self_miniapp_name: str = ""


settings = Settings()
