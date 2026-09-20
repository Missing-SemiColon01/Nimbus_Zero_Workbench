from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Sovereign AI Workbench"
    environment: str = "development"
    data_dir: Path = Path("data")
    models_config: Path = Path("configs/models.yaml")
    agents_config: Path = Path("configs/agents.yaml")
    ollama_base_url: str = "http://ollama:11434"
    sovereign_mode: bool = True
    sandbox_image: str = "workbench-sandbox:latest"
    sandbox_timeout_seconds: int = 30
    sandbox_mem_limit: str = "256m"
    sandbox_cpu_quota: int = 50_000
    sandbox_max_retries: int = 3
    cors_origins: list[str] = ["*"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
