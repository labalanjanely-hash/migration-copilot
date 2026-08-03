from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_prefix="MIGRATION_COPILOT_",
        extra="ignore",
    )
    app_name: str = "Migration Copilot"
    environment: Literal["local", "test", "staging", "production"] = "local"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./migration_copilot.db"
    output_directory: Path = Path("outputs")
    openai_model: str = "gpt-5.6-terra"
    read_only: bool = Field(default=True, frozen=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()

