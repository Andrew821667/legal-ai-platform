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
    news_helper_bot_username: str = "legal_ai_helper_new_bot"
    tz_name: str = "Europe/Moscow"
    openai_api_key: str = ""
    openai_base_url: str = ""
    news_model: str = "deepseek-chat"
    news_top_k: int = 5
    news_schedule_slots: str = "10:00,13:00,17:00"
    news_retry_failed_after_minutes: int = 15
    news_max_per_source: int = 4
    news_generate_limit: int = 5
    news_generate_interval_seconds: int = 1800
    news_publish_interval_seconds: int = 300
    news_generate_interval_options: str = "900,1800,2700,3600,7200"
    news_publish_interval_options: str = "60,120,300,600,900"
    news_generate_limit_options: str = "3,5,7,10"
    news_similarity_threshold: float = 0.48
    news_priority_domains: str = ""
    news_history_scan_limit: int = 120
    news_daily_morning_slot: str = "09:00"
    news_daily_evening_slot: str = "18:00"
    news_weekly_review_slot: str = "15:00"
    news_longread_slot: str = "13:00"
    news_humor_slot: str = "11:00"
    news_daily_morning_options: str = "08:00,08:30,09:00,09:30,10:00"
    news_daily_evening_options: str = "17:00,17:30,18:00,18:30,19:00"
    news_weekly_review_options: str = "14:00,14:30,15:00,15:30,16:00"
    news_longread_options: str = "12:00,12:30,13:00,13:30,14:00"
    news_humor_options: str = "10:00,10:30,11:00,11:30,12:00"
    news_longread_topics: str = (
        "AI для intake и первичной квалификации обращений,"
        "Автоматизация договорной работы и redline-процессов,"
        "AI-поиск по базе знаний и внутренним документам,"
        "AI-комплаенс, privacy и governance для юрфункции,"
        "Использование LLM в судебной и претензионной работе,"
        "Как строить legal ops на базе AI и workflow-движков,"
        "Автоматизация due diligence и проверки контрагентов,"
        "AI-ассистенты для инхаус-команд и юрфирм,"
        "Как упаковать юридический продукт или сервис на базе AI,"
        "Как руководителю юрфункции внедрять AI без потери качества"
    )
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
    google_news_query_ops_ru: str = '("автоматизация договорной работы" OR "автоматизация юротдела" OR legaltech OR "документооборот юристов" OR "AI для юристов")'
    google_news_query_ops_en: str = '("legal operations" OR "contract automation" OR "AI for legal departments" OR "AI for lawyers" OR legaltech)'
    google_news_query_regulation_ru: str = '("регулирование ИИ" OR "закон об ИИ" OR "ответственность за ИИ" OR "персональные данные ИИ" OR "AI compliance")'
    google_news_query_regulation_en: str = '("AI regulation" OR "AI Act" OR "AI compliance" OR "AI governance" OR "AI privacy law")'
    google_news_query_market_en: str = '("legal tech" OR legaltech OR "legal AI" OR "AI contract review" OR "AI compliance platform")'
    google_news_lang_ru: str = "ru"
    google_news_lang_en: str = "en"
    google_news_region_ru: str = "RU"
    google_news_region_en: str = "US"

    @property
    def telegram_channels_list(self) -> list[str]:
        return [item.strip() for item in self.telegram_channels.split(",") if item.strip()]

    @property
    def news_daily_morning_options_list(self) -> list[str]:
        return [item.strip() for item in self.news_daily_morning_options.split(",") if item.strip()]

    @property
    def news_generate_interval_options_list(self) -> list[int]:
        return [int(item.strip()) for item in self.news_generate_interval_options.split(",") if item.strip()]

    @property
    def news_publish_interval_options_list(self) -> list[int]:
        return [int(item.strip()) for item in self.news_publish_interval_options.split(",") if item.strip()]

    @property
    def news_generate_limit_options_list(self) -> list[int]:
        return [int(item.strip()) for item in self.news_generate_limit_options.split(",") if item.strip()]

    @property
    def news_daily_evening_options_list(self) -> list[str]:
        return [item.strip() for item in self.news_daily_evening_options.split(",") if item.strip()]

    @property
    def news_weekly_review_options_list(self) -> list[str]:
        return [item.strip() for item in self.news_weekly_review_options.split(",") if item.strip()]

    @property
    def news_longread_options_list(self) -> list[str]:
        return [item.strip() for item in self.news_longread_options.split(",") if item.strip()]

    @property
    def news_humor_options_list(self) -> list[str]:
        return [item.strip() for item in self.news_humor_options.split(",") if item.strip()]

    @property
    def news_longread_topics_list(self) -> list[str]:
        return [item.strip() for item in self.news_longread_topics.split(",") if item.strip()]

    @property
    def lead_bot_url(self) -> str:
        username = self.lead_bot_username.strip().lstrip("@")
        if not username:
            return ""
        return f"https://t.me/{username}"

    @property
    def news_helper_bot_url(self) -> str:
        username = self.news_helper_bot_username.strip().lstrip("@")
        if not username:
            return ""
        return f"https://t.me/{username}"


settings = Settings()
