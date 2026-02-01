from pathlib import Path
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """API configuration."""

    # App metadata
    APP_NAME: str = "Review Analyzer API"
    VERSION: str = "1.0.0"

    # API config
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"]

    # OpenAI (reuse from existing .env)
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TEMPERATURE: float = 0.2
    OPENAI_MAX_TOKENS: int = 300

    # Storage paths
    STORAGE_ROOT: Path = Path("storage")
    DATASETS_DIR: Path = STORAGE_ROOT / "datasets"
    RUNS_DIR: Path = STORAGE_ROOT / "runs"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    settings = Settings()

    # Ensure storage directories exist at runtime
    settings.DATASETS_DIR.mkdir(parents=True, exist_ok=True)
    settings.RUNS_DIR.mkdir(parents=True, exist_ok=True)

    return settings
