"""KBS Service config."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8200
    CHROMA_URL: str = "http://localhost:8001"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4o-mini"
    NVIDIA_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
