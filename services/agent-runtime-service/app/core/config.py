from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    PORT: int = 8000

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://factory:factory_secret@localhost:5432/factory_db"

    # Redis
    REDIS_URL: str = "redis://:redis_secret@localhost:6379"

    # NATS
    NATS_URL: str = "nats://localhost:4222"

    # AI Providers
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = ""
    OPENROUTER_SITE_URL: str = ""
    OPENROUTER_APP_NAME: str = "smart-factory"
    NVIDIA_API_KEY: str = ""

    # LLM Configuration
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.1

    # Agent Configuration
    MAX_AGENT_STEPS: int = 50
    AGENT_TIMEOUT_SECONDS: int = 300

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
