"""Configuration management using pydantic-settings."""

from typing import Set, Union
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_keys: str = Field(default="", description="Comma-separated list of valid API keys")
    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8000, description="Server port")

    # Codex Configuration
    codex_path: str = Field(default="/opt/homebrew/bin/codex", description="Path to codex binary")
    codex_model: str = Field(default="gpt-5.2-codex", description="Codex model to use")
    codex_sandbox: str = Field(default="read-only", description="Sandbox mode (read-only/workspace-write/danger-full-access)")
    codex_full_auto: bool = Field(default=False, description="Enable full auto mode")

    # Server Configuration
    log_level: str = Field(default="info", description="Logging level")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    @property
    def api_keys_set(self) -> Set[str]:
        """Return API keys as a set."""
        if not self.api_keys:
            return set()
        return set(k.strip() for k in self.api_keys.split(",") if k.strip())


# Global settings instance
settings = Settings()
