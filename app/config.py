"""Configuration management using pydantic-settings."""

import os
import shutil
import sys
from typing import Set
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_default_cli_path(cli_name: str) -> str:
    """
    Detect CLI binary path across platforms.

    Args:
        cli_name: Name of the CLI binary (e.g., 'codex', 'opencode')

    Returns:
        Path to the binary, or just the name if not found (relies on PATH)
    """
    # Try to find in PATH first
    cli_in_path = shutil.which(cli_name)
    if cli_in_path:
        return cli_in_path

    # Platform-specific fallback paths
    if sys.platform == "darwin":  # macOS
        homebrew_paths = [
            f"/opt/homebrew/bin/{cli_name}",  # Apple Silicon
            f"/usr/local/bin/{cli_name}"       # Intel Mac
        ]
        for path in homebrew_paths:
            if os.path.exists(path):
                return path
    elif sys.platform == "win32":  # Windows
        # Check common Windows installation paths
        windows_paths = [
            os.path.expandvars(f"%LOCALAPPDATA%\\{cli_name}\\{cli_name}.exe"),
            os.path.expandvars(f"%PROGRAMFILES%\\{cli_name}\\{cli_name}.exe"),
        ]
        for path in windows_paths:
            if os.path.exists(path):
                return path
    else:  # Linux and others
        linux_paths = [
            f"/usr/local/bin/{cli_name}",
            f"/usr/bin/{cli_name}",
            os.path.expanduser(f"~/.local/bin/{cli_name}")
        ]
        for path in linux_paths:
            if os.path.exists(path):
                return path

    # Fallback to just the name (rely on PATH)
    return cli_name


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Configuration
    api_keys: str = Field(default="", description="Comma-separated list of valid API keys")
    host: str = Field(default="0.0.0.0", description="Server bind address")
    port: int = Field(default=8000, description="Server port")

    # Codex Configuration
    codex_path: str = Field(default="", description="Path to codex binary (empty = auto-detect)")
    codex_model: str = Field(default="o3", description="Codex model to use")
    codex_sandbox: str = Field(default="read-only", description="Sandbox mode (read-only/workspace-write/danger-full-access)")
    codex_full_auto: bool = Field(default=False, description="Enable full auto mode")

    # OpenCode Configuration
    opencode_path: str = Field(default="", description="Path to opencode binary (empty = auto-detect)")
    opencode_model: str = Field(default="opencode/grok-code", description="OpenCode model (format: provider/model)")

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

    @property
    def resolved_codex_path(self) -> str:
        """Get resolved codex path with auto-detection."""
        if self.codex_path:
            return self.codex_path
        return _get_default_cli_path("codex")

    @property
    def resolved_opencode_path(self) -> str:
        """Get resolved opencode path with auto-detection."""
        if self.opencode_path:
            return self.opencode_path
        return _get_default_cli_path("opencode")


# Global settings instance
settings = Settings()
