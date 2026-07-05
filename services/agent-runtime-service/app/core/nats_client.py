import structlog
import nats
from nats.aio.client import Client as NATSClient
from typing import Callable, Optional

logger = structlog.get_logger()


class NatsClientWrapper:
    """NATS client wrapper with reconnection logic."""

    def __init__(self):
        self._client: Optional[NATSClient] = None

    @property
    def client(self) -> NATSClient:
        if not self._client:
            raise RuntimeError("NATS client not connected")
        return self._client

    async def connect(self):
        from app.core.config import settings
        try:
            self._client = await nats.connect(
                settings.NATS_URL,
                reconnect_time_wait=2,
                max_reconnect_attempts=-1,
                error_cb=self._error_cb,
                disconnected_cb=self._disconnected_cb,
                reconnected_cb=self._reconnected_cb,
            )
            logger.info("✅ Connected to NATS", url=settings.NATS_URL)
        except Exception as e:
            logger.error("❌ NATS connection failed", error=str(e))
            raise

    async def disconnect(self):
        if self._client:
            await self._client.drain()
            logger.info("NATS connection closed")

    async def publish(self, subject: str, payload: dict):
        import json
        data = json.dumps(payload).encode()
        await self.client.publish(subject, data)

    async def subscribe(self, subject: str, callback: Callable):
        return await self.client.subscribe(subject, cb=callback)

    async def _error_cb(self, e):
        logger.error("NATS error", error=str(e))

    async def _disconnected_cb(self):
        logger.warning("NATS disconnected")

    async def _reconnected_cb(self):
        logger.info("NATS reconnected")


nats_client = NatsClientWrapper()
