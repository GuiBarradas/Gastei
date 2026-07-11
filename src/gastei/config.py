"""Centralized configuration via ``pydantic-settings``.

Reads from the ``.env`` file at the project root and from the process
environment. This is the single point where environment variables enter
the codebase; the rest of the code imports ``settings`` from here.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_env: Literal["development", "production", "test"] = "development"
    database_url: str = "sqlite:///./data/gastei.db"
    secret_key: str = Field(default="", description="Fernet key (base64). Required in production.")

    # LLM provider
    llm_provider: Literal["anthropic", "gemini", "none"] = "anthropic"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model_fast: str = "claude-haiku-4-5"
    anthropic_model_smart: str = "claude-opus-4-7"

    # Rolling "-latest" aliases: pinned Gemini versions get retired and 404.
    # FAST rides the lite tier — cheaper, with more spare free-tier capacity.
    google_api_key: str = ""
    gemini_model_fast: str = "gemini-flash-lite-latest"
    gemini_model_smart: str = "gemini-flash-latest"

    # Pluggy
    pluggy_client_id: str = ""
    pluggy_client_secret: str = ""
    pluggy_base_url: str = "https://api.pluggy.ai"

    # Sync
    sync_interval_hours: int = 6
    enable_scheduler: bool = False  # opt-in: True in production, False in dev/test.


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached singleton. Always prefer this over instantiating ``Settings()`` directly."""
    return Settings()
