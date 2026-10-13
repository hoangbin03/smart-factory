"""Nexus Service — Core Config."""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8100

    DATABASE_URL: str = "postgresql+asyncpg://factory:factory_secret@localhost:5432/factory_db"
    REDIS_URL: str = "redis://:redis_secret@localhost:6379"
    NATS_URL: str = "nats://localhost:4222"
    KBS_URL: str = "http://localhost:8200"

    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_SITE_URL: str = "http://localhost:8080"
    OPENROUTER_APP_NAME: str = "smart-factory-nexus"

    NVIDIA_API_KEY: str = ""
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"

    # Project workspaces (shared volume, read-only) + agent-runtime for git imports
    WORKSPACE_ROOT: str = "/workspaces"
    AGENT_RUNTIME_URL: str = "http://agent-runtime-service:8000"

    class Config:
        env_file = ".env"


settings = Settings()
