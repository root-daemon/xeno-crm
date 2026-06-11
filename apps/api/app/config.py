from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./xeno_dev.db"
    worker_url: str = "http://localhost:9000"
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    run_migrations_on_startup: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
