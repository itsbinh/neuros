"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # inference
    lts1_base_url: str = "http://lts1:8000"
    lts1_embed_url: str = "http://lts1:8005"
    mac_mini_url: str = "http://mac:8001"
    model_fast: str = "qwen35"
    model_vision: str = "qwen27-vision"
    model_local: str = "gemma-4-e2b"

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

    # NAS
    nas_base_url: str = ""  # will default to http://nas:5000 at runtime if empty
    nas_user: str = "admin"  # from env NAS_USER
    nas_password: str = ""  # from env NAS_PASSWORD

    # SSH users per host
    ssh_user_lts1: str = "neuros"  # from env SSH_USER_LTS1
    ssh_user_lts2: str = "neuros"  # from env SSH_USER_LTS2

    # Neo4j
    neo4j_uri: str = "bolt://lts2:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "neuros_neo4j_pass"  # from env NEO4J_PASSWORD

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
