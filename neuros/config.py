"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # inference
    lts1_base_url: str = "http://lts1:8000"
    lts1_embed_url: str = "http://lts1:8005"
    mac_mini_url: str = "http://mac:8001"
    model_fast: str = "qwen3-35b-a3b"
    model_vision: str = "qwen3-27b"
    model_local: str = "gemma-4"

    # services
    qdrant_url: str = "http://lts2:6333"
    redis_url: str = "redis://lts2:6379"
    postgres_dsn: str = "postgresql+asyncpg://neuros:password@lts2:5432/neuros"
    searxng_url: str = "http://lts2:8888"

    # ssh
    ssh_key_path: str = "~/.ssh/id_ed25519"
    lts1_host: str = "lts1"
    lts2_host: str = "lts2"
    nas_host: str = "nas"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
