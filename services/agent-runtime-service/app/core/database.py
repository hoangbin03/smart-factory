import structlog
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.core.config import settings

logger = structlog.get_logger()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.ENVIRONMENT == "development",
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Initialize database connection."""
    try:
        async with engine.connect() as conn:
            logger.info("✅ Database connection established")
    except Exception as e:
        logger.error("❌ Database connection failed", error=str(e))
        raise


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
