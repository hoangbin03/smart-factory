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

    # Knowledge Base Service (RAG) — used for agent long-term memory
    KBS_URL: str = "http://kbs-service:8200"

    # LLM Configuration
    DEFAULT_MODEL: str = "openai/gpt-4o-mini"
    MAX_TOKENS: int = 8192
    TEMPERATURE: float = 0.1

    # Agent Configuration
    MAX_AGENT_STEPS: int = 50
    AGENT_TIMEOUT_SECONDS: int = 300

    # Workspace / Tool Layer
    WORKSPACE_ROOT: str = "/workspaces"
    TOOL_COMMAND_TIMEOUT: int = 120
    MAX_REWORK_ROUNDS: int = 2

    # NVIDIA NeMo Agent Toolkit (NAT) runtime
    USE_NAT_DEVELOPER: bool = False   # run Developer Agent via NAT ReAct agent + tool functions
    NAT_MAX_TOOL_CALLS: int = 16
    # Comma-separated agent roles to run through the NAT ReAct agent (beyond developer),
    # e.g. "reviewer,qa,architect,planner". Empty = only the developer uses NAT.
    USE_NAT_AGENTS: str = ""

    # Agent long-term memory (RAG). When on, agents retrieve relevant past
    # knowledge before working and persist key decisions/outputs after.
    ENABLE_AGENT_MEMORY: bool = True
    MEMORY_TOP_K: int = 4

    # Real deployment (DevOps agent actually builds & runs a Docker container).
    # Requires the Docker socket mounted into this container. OFF by default —
    # it grants the runtime real Docker access on the host.
    ENABLE_REAL_DEPLOY: bool = False
    DEPLOY_PORT_MIN: int = 9100
    DEPLOY_PORT_MAX: int = 9199
    DEPLOY_HOST: str = "localhost"
    DEPLOY_IMAGE_PREFIX: str = "factory-preview"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
