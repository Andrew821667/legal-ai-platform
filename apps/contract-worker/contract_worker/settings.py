from __future__ import annotations

import socket

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    core_api_url: str = "http://core-api:8000"
    api_key_worker: str = ""
    worker_id: str = socket.gethostname()
    job_timeout_seconds: int = 1200


settings = Settings()
