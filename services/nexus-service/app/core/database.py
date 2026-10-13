"""Nexus — Async database session (SQLAlchemy + asyncpg)."""
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.core.config import settings
import structlog

logger = structlog.get_logger()
_engine = None
_session_factory = None


async def init_db():
    global _engine, _session_factory
    _engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    logger.info("Nexus DB connected")


@asynccontextmanager
async def get_session():
    async with _session_factory() as session:
        yield session
