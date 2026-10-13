"""Nexus - Agent config endpoints (CRUD agent personality + AI runtime settings)."""
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import get_session

router = APIRouter()

DEFAULT_AI_CONFIG: Dict[str, Any] = {
    "provider": "openrouter",
    "model": "openai/gpt-4o-mini",
    "temperature": 0.1,
    "top_p": 1,
    "max_tokens": 4096,
    "presence_penalty": 0,
    "frequency_penalty": 0,
}

NEXUS_AI_CONFIG: Dict[str, Any] = {
    **DEFAULT_AI_CONFIG,
    "temperature": 0.3,
    "max_tokens": 2048,
}


class AgentConfigUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    capabilities: Optional[List[str]] = None
    tools: Optional[List[str]] = None
    config: Optional[Dict[str, Any]] = None
    status: Optional[str] = None


async def ensure_nexus_agent(session) -> None:
    await session.execute(
        text(
            """
            INSERT INTO agents (agent_id, name, description, role, runtime, capabilities, tools, status, config)
            VALUES (
                'nexus_agent',
                'Nexus AI Master',
                'Master Intelligence Agent. Monitors and controls the smart factory.',
                'master_intelligence',
                'nemo',
                ARRAY['monitoring', 'analysis', 'reporting', 'coordination'],
                ARRAY['search_tool', 'documentation_tool'],
                'HEALTHY',
                CAST(:config AS JSONB)
            )
            ON CONFLICT (agent_id) DO NOTHING
            """
        ),
        {"config": json.dumps({"ai": NEXUS_AI_CONFIG})},
    )


def normalize_config(value: Any, agent_id: str) -> Dict[str, Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    config = value if isinstance(value, dict) else {}
    defaults = NEXUS_AI_CONFIG if agent_id == "nexus_agent" else DEFAULT_AI_CONFIG
    ai_config = config.get("ai") if isinstance(config.get("ai"), dict) else {}
    return {**config, "ai": {**defaults, **ai_config}}


def row_to_agent(row: Any) -> Dict[str, Any]:
    data = dict(row)
    data["config"] = normalize_config(data.get("config"), data.get("agent_id", ""))
    return data


@router.get("/")
async def list_agents():
    async with get_session() as session:
        await ensure_nexus_agent(session)
        await session.commit()
        result = await session.execute(text("""
            SELECT id, agent_id, name, description, role, runtime,
                   capabilities, tools, status, config, version,
                   last_seen_at, created_at, updated_at
            FROM agents ORDER BY role
        """))
        rows = result.mappings().all()
        return {"data": [row_to_agent(r) for r in rows], "total": len(rows)}


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    async with get_session() as session:
        if agent_id == "nexus_agent":
            await ensure_nexus_agent(session)
            await session.commit()
        result = await session.execute(
            text("SELECT * FROM agents WHERE agent_id = :id"),
            {"id": agent_id},
        )
        row = result.mappings().first()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return row_to_agent(row)


@router.patch("/{agent_id}")
async def update_agent(agent_id: str, body: AgentConfigUpdate):
    """Update agent config - identity, tools, status and AI runtime settings."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")

    system_prompt = updates.pop("system_prompt", None)
    if system_prompt is not None:
        next_config = updates.get("config") or {}
        next_config["system_prompt"] = system_prompt
        updates["config"] = next_config

    allowed_columns = {"name", "description", "capabilities", "tools", "config", "status"}
    updates = {key: value for key, value in updates.items() if key in allowed_columns}
    if not updates:
        raise HTTPException(400, "No supported fields to update")

    set_clauses = []
    params: Dict[str, Any] = {"agent_id": agent_id}
    for key, value in updates.items():
        if key == "config":
            set_clauses.append("config = CAST(:config AS JSONB)")
            params["config"] = json.dumps(value)
        else:
            set_clauses.append(f"{key} = :{key}")
            params[key] = value

    async with get_session() as session:
        if agent_id == "nexus_agent":
            await ensure_nexus_agent(session)
        result = await session.execute(
            text(f"""
                UPDATE agents SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE agent_id = :agent_id
                RETURNING *
            """),
            params,
        )
        await session.commit()
        row = result.mappings().first()
        if not row:
            raise HTTPException(404, f"Agent '{agent_id}' not found")
        return row_to_agent(row)


@router.get("/{agent_id}/stats")
async def agent_stats(agent_id: str):
    async with get_session() as session:
        result = await session.execute(text("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed,
                COUNT(*) FILTER (WHERE status = 'FAILED') AS failed,
                COUNT(*) FILTER (WHERE status = 'RUNNING') AS running,
                COUNT(*) AS total
            FROM tasks WHERE agent_id = :id
        """), {"id": agent_id})
        row = result.mappings().first()
        return dict(row) if row else {}