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
    allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        alias="ALLOWED_ORIGINS",
    )
    demo_mode: bool = Field(default=True, alias="DEMO_MODE")
    fast_demo_db: bool = Field(default=True, alias="FAST_DEMO_DB")
    model_dir: Path = Field(default=_REPO_ROOT / "ml" / "artifacts", alias="MODEL_DIR")

    @property
    def effective_database_url(self) -> str:
        """Use ultra-fast local SQLite in demo mode unless FAST_DEMO_DB=false is set."""
        if self.demo_mode and self.fast_demo_db:
            return "sqlite:///./careloop.db"
        return self.database_url

    @property
    def resolved_model_dir(self) -> Path:
        """Resolve model_dir reliably whether relative to repo root, cwd, or absolute."""
        if self.model_dir.is_absolute() and self.model_dir.exists():
            return self.model_dir
        from_root = (_REPO_ROOT / self.model_dir).resolve()
        if from_root.exists():
            return from_root
        from_cwd = (Path.cwd() / self.model_dir).resolve()
        if from_cwd.exists():
            return from_cwd
        return (_REPO_ROOT / "ml" / "artifacts").resolve()

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
