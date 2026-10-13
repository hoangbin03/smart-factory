"""Nexus — NATS client (shared singleton)."""
import json
from typing import Any, Callable, Dict, Optional
import nats
from nats.aio.client import Client
import structlog
from app.core.config import settings

logger = structlog.get_logger()


class NatsClient:
    def __init__(self):
        self._nc: Optional[Client] = None

    async def connect(self):
        self._nc = await nats.connect(settings.NATS_URL)
        logger.info("Nexus connected to NATS", url=settings.NATS_URL)

    async def disconnect(self):
        if self._nc:
            await self._nc.drain()

    async def subscribe(self, subject: str, handler: Callable):
        if not self._nc:
            raise RuntimeError("NATS not connected")
        # Use wildcard subscription
        sub = await self._nc.subscribe(subject, cb=handler)
        logger.info("NATS subscribed", subject=subject)
        return sub

    async def publish(self, subject: str, data: Dict[str, Any]):
        if not self._nc:
            return
        await self._nc.publish(subject, json.dumps(data, default=str).encode())


nats_client = NatsClient()
