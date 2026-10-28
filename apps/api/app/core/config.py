"""Application settings loaded from environment variables (pydantic-settings)."""
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    """All runtime configuration. Secrets are never hard-coded; see .env.example."""

    model_config = SettingsConfigDict(
        env_file=(str(_REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "CareLoop AI"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    database_url: str = Field(default="sqlite:///./careloop.db", alias="DATABASE_URL")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    llm_model: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL")
    cron_token: SecretStr | None = Field(default=None, alias="CRON_TOKEN")
    allowed_origins: str = Field(default="http://localhost:3000", alias="ALLOWED_ORIGINS")
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    model_dir: Path = Field(default=_REPO_ROOT / "ml" / "artifacts", alias="MODEL_DIR")

    @property
    def cors_origins(self) -> list[str]:
        """ALLOWED_ORIGINS is a comma-separated list of exact origins."""
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_enabled(self) -> bool:
        """True when a Groq key is configured; otherwise templates are used."""
        return bool(self.groq_api_key and self.groq_api_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    settings = Settings()
    logger.debug("settings loaded", extra={"demo_mode": settings.demo_mode})
    return settings
