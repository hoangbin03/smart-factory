import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from app.core.config import settings
from app.core.database import init_db
from app.core.nats_client import nats_client
from app.api.v1.router import api_router
from app.runtime.agent_runner import AgentRunner

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("🚀 Agent Runtime Service starting...")

    # Initialize database
    await init_db()

    # Connect to NATS
    await nats_client.connect()

    # Initialize agent runner (subscribe to NATS events)
    runner = AgentRunner()
    await runner.start()

    logger.info(
        "✅ Agent Runtime Service ready",
        port=settings.PORT,
        environment=settings.ENVIRONMENT,
    )

    yield

    # Cleanup
    logger.info("🛑 Agent Runtime Service shutting down...")
    await runner.stop()
    await nats_client.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Runtime Service",
        description="NVIDIA NeMo-integrated AI Agent Runtime for Factory Platform",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routes
    app.include_router(api_router, prefix="/api/v1")

    # Prometheus metrics
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "healthy", "service": "agent-runtime-service"}

    return app


app = create_app()
