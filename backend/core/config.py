from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sovereign AI Workbench"
    environment: str = "development"
    data_dir: Path = Path("data")
    models_config: Path = Path("configs/models.yaml")
    ollama_base_url: str = "http://ollama:11434"
    sovereign_mode: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
