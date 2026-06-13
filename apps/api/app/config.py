from __future__ import annotations

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:///./xeno_dev.db"
    worker_url: str = "http://localhost:9000"
    receipt_callback_url: str = "http://localhost:8000/receipts"
    # AI — single OpenRouter gateway (OpenAI-compatible API).
    openrouter_api_key: Optional[str] = None
    openrouter_model: str = "google/gemini-2.5-flash"
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    run_migrations_on_startup: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url_alchemy(self) -> str:
        """Convert postgres:// or postgresql:// to the psycopg3 driver prefix."""
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://"):]
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://"):]
        return url


settings = Settings()
