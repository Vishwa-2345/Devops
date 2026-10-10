"""Application configuration loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    """Runtime settings. All values are environment-overridable."""

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "SelfHealOps"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")

    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    database_url: str = "sqlite:///./data/selfhealops.db"

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # GitHub
    github_token: str = ""
    github_api_base_url: str = "https://api.github.com"
    github_request_timeout: float = 10.0
    github_max_pages: int = 5
    github_per_page: int = 50

    # LLM
    llm_provider: str = "rules"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    ollama_timeout: float = 30.0

    # Monitoring
    poll_interval_seconds: int = 0

    # Security limits
    max_log_chars: int = 60000
    max_request_body_bytes: int = 1_048_576

    @field_validator("cors_origins")
    @classmethod
    def _strip_origins(cls, value: str) -> str:
        return value.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def github_configured(self) -> bool:
        return bool(self.github_token.strip())

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
