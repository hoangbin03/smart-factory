"""Shared helpers for reading per-agent AI settings."""
import json
from typing import Any, Dict

import structlog
from sqlalchemy import text

from app.core.database import get_session

logger = structlog.get_logger()


async def load_agent_ai_config(agent_id: str = "nexus_agent") -> Dict[str, Any]:
    try:
        async with get_session() as session:
            result = await session.execute(
                text("SELECT config FROM agents WHERE agent_id = :agent_id"),
                {"agent_id": agent_id},
            )
            row = result.mappings().first()
            config = row.get("config") if row else None
            if isinstance(config, str):
                config = json.loads(config)
            if isinstance(config, dict) and isinstance(config.get("ai"), dict):
                return config["ai"]
    except Exception as exc:
        logger.warning("Failed to load agent AI config, using defaults", agent_id=agent_id, error=str(exc))
    return {}