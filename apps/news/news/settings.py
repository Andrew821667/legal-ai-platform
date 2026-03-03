from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    core_api_url: str = "http://core-api:8000"
    api_key_news: str = ""
    api_key_admin: str = ""
    telegram_bot_token: str = ""
    news_admin_bot_token: str = ""
    telegram_channel_id: str = ""
    telegram_channel_username: str = ""
    news_discussion_chat_id: str = ""
    news_discussion_chat_username: str = ""
    news_admin_ids: str = ""
    news_source_keys: str = ""
    news_source_urls: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_session_name: str = "apps/news/legacy/telegram_bot"
    telegram_channels: str = ""
    telegram_fetch_limit: int = 50
    telegram_fetch_enabled: bool = True
    lead_bot_username: str = "LegalAI_Popov_Andrew"
    tz_name: str = "Europe/Moscow"
    openai_api_key: str = ""
    openai_base_url: str = ""
    news_model: str = "deepseek-chat"
    news_top_k: int = 5
    news_schedule_slots: str = "10:00,13:00,17:00"
    news_retry_failed_after_minutes: int = 15
    news_max_per_source: int = 3
    news_generate_limit: int = 5
    news_generate_interval_seconds: int = 1800
    news_publish_interval_seconds: int = 300
    news_similarity_threshold: float = 0.48
    news_priority_domains: str = ""
    news_history_scan_limit: int = 120
    news_weekday_slots: str = "10:00,16:30"
    news_saturday_slots: str = "11:00"
    news_sunday_slots: str = ""
    news_alert_slot: str = "19:00"
    news_enable_alert_slot: bool = True
    news_deep_days: str = "tue,thu"
    news_digest_weekday: int = 5
    news_cta_sequence: str = "soft,soft,soft,soft,soft,soft,soft,mid,mid,hard"
    google_news_query_ru: str = '("искусственный интеллект" OR "юридический ИИ" OR legaltech OR "автоматизация юротдела" OR "автоматизация юридической функции")'
    google_news_query_en: str = '("legal AI" OR legaltech OR "AI for lawyers" OR "contract automation" OR "legal operations automation")'
    google_news_lang_ru: str = "ru"
    google_news_lang_en: str = "en"
    google_news_region_ru: str = "RU"
    google_news_region_en: str = "US"

    @property
    def telegram_channels_list(self) -> list[str]:
        return [item.strip() for item in self.telegram_channels.split(",") if item.strip()]

    @property
    def lead_bot_url(self) -> str:
        username = self.lead_bot_username.strip().lstrip("@")
        if not username:
            return ""
        return f"https://t.me/{username}"


settings = Settings()
