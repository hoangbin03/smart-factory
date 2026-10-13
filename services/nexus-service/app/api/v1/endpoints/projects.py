"""Nexus — Project management + per-project Knowledge Graph."""
import json
from typing import Any, Dict, List, Optional

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.core.database import get_session
from app.core.llm_client import llm_client
from app.kg import build_knowledge_graph

logger = structlog.get_logger()
router = APIRouter()

_TABLES_READY = False


async def ensure_project_tables() -> None:
    """Idempotently create the projects + knowledge-graph tables (existing DBs)."""
    global _TABLES_READY
    if _TABLES_READY:
        return
    async with get_session() as session:
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS projects (
              id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
              name VARCHAR(255) NOT NULL,
              description TEXT DEFAULT '',
              source_type VARCHAR(20) NOT NULL DEFAULT 'empty',
              repo_url TEXT DEFAULT '',
              status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
              config JSONB DEFAULT '{}',
              kg_status VARCHAR(20) NOT NULL DEFAULT 'NONE',
              kg_built_at TIMESTAMPTZ,
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )"""))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS kg_nodes (
              id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
              project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              node_key VARCHAR(500) NOT NULL,
              label VARCHAR(500) NOT NULL,
              type VARCHAR(40) NOT NULL DEFAULT 'concept',
              meta JSONB DEFAULT '{}',
              created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
              UNIQUE (project_id, node_key)
            )"""))
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS kg_edges (
              id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
              project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
              source_key VARCHAR(500) NOT NULL,
              target_key VARCHAR(500) NOT NULL,
              relation VARCHAR(40) NOT NULL DEFAULT 'relates_to',
              meta JSONB DEFAULT '{}'
            )"""))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_kg_nodes_project ON kg_nodes(project_id)"))
        await session.execute(text("CREATE INDEX IF NOT EXISTS idx_kg_edges_project ON kg_edges(project_id)"))
        # Link workflows to their owning project (a project "contains" workflows).
        await session.execute(text("ALTER TABLE workflows ADD COLUMN IF NOT EXISTS project_id UUID"))
        # Clear any dangling references, then add the FK (delete project -> delete its runs).
        await session.execute(text(
            "UPDATE workflows SET project_id = NULL WHERE project_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM projects p WHERE p.id = workflows.project_id)"
        ))
        await session.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_workflows_project') THEN
                ALTER TABLE workflows ADD CONSTRAINT fk_workflows_project
                  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE;
              END IF;
            END $$;
        """))
        await session.commit()
    _TABLES_READY = True


class ProjectCreate(BaseModel):
    name: str
    description: str = ""
    source_type: str = "empty"          # empty | git | folder
    repo_url: str = ""
    branch: str = ""
    token: str = ""


class KGQuery(BaseModel):
    query: str


async def _runtime_post(path: str, body: dict, timeout: int = 240) -> tuple[int, dict]:
    url = f"{settings.AGENT_RUNTIME_URL.rstrip('/')}{path}"
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.post(url, json=body)
    try:
        return r.status_code, r.json()
    except Exception:  # noqa: BLE001
        return r.status_code, {"raw": r.text[:500]}


# ── CRUD ────────────────────────────────────────────────────────────────────
@router.post("/")
async def create_project(body: ProjectCreate):
    await ensure_project_tables()
    source = body.source_type if body.source_type in ("empty", "git", "folder") else "empty"
    async with get_session() as session:
        row = (await session.execute(
            text("INSERT INTO projects (name, description, source_type, repo_url) "
                 "VALUES (:n, :d, :s, :r) RETURNING *"),
            {"n": body.name.strip() or "Untitled project", "d": body.description,
             "s": source, "r": body.repo_url.strip()},
        )).mappings().first()
        await session.commit()
    project = dict(row)
    pid = str(project["id"])

    # Clone immediately when created from a git URL, so code is ready to work on.
    if source == "git" and body.repo_url.strip():
        status, data = await _runtime_post(
            f"/api/v1/workspace/{pid}/import/git",
            {"repo_url": body.repo_url.strip(), "branch": body.branch, "token": body.token},
        )
        project["import"] = {"ok": status == 200, "detail": data}
    return project


@router.get("/")
async def list_projects(page: int = Query(1, ge=1), limit: int = Query(50, le=200)):
    await ensure_project_tables()
    offset = (page - 1) * limit
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT p.*,
                   (SELECT COUNT(*) FROM kg_nodes n WHERE n.project_id = p.id) AS node_count,
                   (SELECT COUNT(*) FROM kg_edges e WHERE e.project_id = p.id) AS edge_count
            FROM projects p ORDER BY p.created_at DESC LIMIT :l OFFSET :o
        """), {"l": limit, "o": offset})).mappings().all()
        total = (await session.execute(text("SELECT COUNT(*) FROM projects"))).scalar()
    return {"data": [dict(r) for r in rows], "total": total, "page": page, "limit": limit}


@router.get("/{project_id}")
async def get_project(project_id: str):
    await ensure_project_tables()
    async with get_session() as session:
        row = (await session.execute(
            text("SELECT * FROM projects WHERE id = :id"), {"id": project_id}
        )).mappings().first()
    if not row:
        raise HTTPException(404, "Project not found")
    return dict(row)


@router.delete("/{project_id}")
async def delete_project(project_id: str):
    await ensure_project_tables()
    async with get_session() as session:
        await session.execute(text("DELETE FROM projects WHERE id = :id"), {"id": project_id})
        await session.commit()
    return {"ok": True}


# ── Import (proxy to agent-runtime, which owns git + the workspace volume) ────
@router.post("/{project_id}/import/git")
async def import_git(project_id: str, body: ProjectCreate):
    await ensure_project_tables()
    status, data = await _runtime_post(
        f"/api/v1/workspace/{project_id}/import/git",
        {"repo_url": body.repo_url.strip(), "branch": body.branch, "token": body.token},
    )
    if status != 200:
        raise HTTPException(status, str(data)[:500])
    return data


class UploadImport(BaseModel):
    files: List[Dict[str, str]]
    replace: bool = True


@router.post("/{project_id}/import/upload")
async def import_upload(project_id: str, body: UploadImport):
    await ensure_project_tables()
    status, data = await _runtime_post(
        f"/api/v1/workspace/{project_id}/import/upload",
        {"files": body.files, "replace": body.replace},
    )
    if status != 200:
        raise HTTPException(status, str(data)[:500])
    return data


# ── Knowledge Graph ──────────────────────────────────────────────────────────
class RunCreate(BaseModel):
    goal: str
    name: str = ""
    agents: List[str] = ["developer_agent", "reviewer_agent", "qa_agent"]


_VALID_AGENTS = {"architect_agent", "planner_agent", "developer_agent",
                 "reviewer_agent", "qa_agent", "devops_agent"}


@router.post("/{project_id}/workflows")
async def create_run(project_id: str, body: RunCreate):
    """Create a workflow (a 'run') that operates on this project's shared workspace."""
    await ensure_project_tables()
    goal = body.goal.strip()
    if not goal:
        raise HTTPException(400, "goal is required")
    agents = [a for a in body.agents if a in _VALID_AGENTS] or ["developer_agent", "reviewer_agent"]
    name = body.name.strip() or goal[:60]
    async with get_session() as session:
        proj = (await session.execute(text("SELECT id FROM projects WHERE id=:id"), {"id": project_id})).first()
        if not proj:
            raise HTTPException(404, "Project not found")
        wf = (await session.execute(
            text("INSERT INTO workflows (name, status, goal, project_id) "
                 "VALUES (:n, 'PENDING', :g, :p) RETURNING id"),
            {"n": name, "g": goal, "p": project_id},
        )).mappings().first()
        wid = str(wf["id"])
        for order, agent in enumerate(agents):
            await session.execute(
                text("INSERT INTO tasks (workflow_id, name, status, agent_id, goal, input, \"order\") "
                     "VALUES (:w, :n, 'PENDING', :a, :g, CAST(:i AS jsonb), :o)"),
                {"w": wid, "n": agent.replace("_agent", "").title(), "a": agent, "g": goal,
                 "i": json.dumps({"workflowGoal": goal, "workflowConfig": {}, "projectId": project_id}),
                 "o": order},
            )
        await session.commit()
    return {"id": wid, "name": name, "goal": goal, "agents": agents, "status": "PENDING"}


@router.get("/{project_id}/workflows")
async def list_runs(project_id: str):
    await ensure_project_tables()
    async with get_session() as session:
        rows = (await session.execute(text("""
            SELECT w.id, w.name, w.status, w.goal, w.created_at, w.started_at,
                   COUNT(t.id) AS task_count,
                   COUNT(t.id) FILTER (WHERE t.status='COMPLETED') AS tasks_done
            FROM workflows w LEFT JOIN tasks t ON t.workflow_id = w.id
            WHERE w.project_id = :p GROUP BY w.id ORDER BY w.created_at DESC
        """), {"p": project_id})).mappings().all()
    return {"data": [dict(r) for r in rows]}


@router.post("/{project_id}/workflows/{workflow_id}/start")
async def start_run(project_id: str, workflow_id: str):
    async with get_session() as session:
        res = await session.execute(
            text("UPDATE workflows SET status='RUNNING', started_at=NOW() "
                 "WHERE id=:w AND project_id=:p AND status='PENDING'"),
            {"w": workflow_id, "p": project_id},
        )
        await session.commit()
    if res.rowcount == 0:
        raise HTTPException(400, "Workflow not found or not startable")
    return {"ok": True, "status": "RUNNING"}


@router.post("/{project_id}/kg/generate")
async def generate_kg(project_id: str):
    await ensure_project_tables()
    async with get_session() as session:
        await session.execute(text("UPDATE projects SET kg_status='BUILDING' WHERE id=:id"),
                              {"id": project_id})
        await session.commit()

    graph = await build_knowledge_graph(project_id)
    if not graph.get("ok"):
        async with get_session() as session:
            await session.execute(text("UPDATE projects SET kg_status='FAILED' WHERE id=:id"),
                                  {"id": project_id})
            await session.commit()
        raise HTTPException(400, graph.get("error", "KG build failed"))

    async with get_session() as session:
        await session.execute(text("DELETE FROM kg_nodes WHERE project_id=:id"), {"id": project_id})
        await session.execute(text("DELETE FROM kg_edges WHERE project_id=:id"), {"id": project_id})
        for n in graph["nodes"]:
            await session.execute(
                text("INSERT INTO kg_nodes (project_id, node_key, label, type, meta) "
                     "VALUES (:p, :k, :l, :t, CAST(:m AS jsonb)) ON CONFLICT DO NOTHING"),
                {"p": project_id, "k": n["key"][:500], "l": str(n["label"])[:500],
                 "t": n["type"], "m": json.dumps(n.get("meta", {}))},
            )
        for e in graph["edges"]:
            await session.execute(
                text("INSERT INTO kg_edges (project_id, source_key, target_key, relation, meta) "
                     "VALUES (:p, :s, :t, :r, CAST(:m AS jsonb))"),
                {"p": project_id, "s": e["source"][:500], "t": e["target"][:500],
                 "r": e["relation"], "m": json.dumps(e.get("meta", {}))},
            )
        await session.execute(
            text("UPDATE projects SET kg_status='READY', kg_built_at=NOW() WHERE id=:id"),
            {"id": project_id},
        )
        await session.commit()
    return {"ok": True, "stats": graph["stats"]}


@router.get("/{project_id}/kg")
async def get_kg(project_id: str):
    await ensure_project_tables()
    async with get_session() as session:
        nodes = (await session.execute(
            text("SELECT node_key, label, type, meta FROM kg_nodes WHERE project_id=:id"),
            {"id": project_id},
        )).mappings().all()
        edges = (await session.execute(
            text("SELECT source_key, target_key, relation FROM kg_edges WHERE project_id=:id"),
            {"id": project_id},
        )).mappings().all()
    return {
        "nodes": [{"key": n["node_key"], "label": n["label"], "type": n["type"], "meta": n["meta"]} for n in nodes],
        "edges": [{"source": e["source_key"], "target": e["target_key"], "relation": e["relation"]} for e in edges],
    }


async def _kg_context(project_id: str, limit: int = 400) -> str:
    """A compact text rendering of the KG for LLM grounding."""
    async with get_session() as session:
        nodes = (await session.execute(
            text("SELECT node_key, label, type FROM kg_nodes WHERE project_id=:id LIMIT :l"),
            {"id": project_id, "l": limit},
        )).mappings().all()
        edges = (await session.execute(
            text("SELECT source_key, target_key, relation FROM kg_edges WHERE project_id=:id LIMIT :l"),
            {"id": project_id, "l": limit},
        )).mappings().all()
    node_lines = "\n".join(f"- [{n['type']}] {n['label']} ({n['node_key']})" for n in nodes)
    edge_lines = "\n".join(f"- {e['source_key']} --{e['relation']}--> {e['target_key']}" for e in edges)
    return f"NODES:\n{node_lines}\n\nRELATIONSHIPS:\n{edge_lines}"


@router.post("/{project_id}/kg/query")
async def query_kg(project_id: str, body: KGQuery):
    await ensure_project_tables()
    ctx = await _kg_context(project_id)
    if "NODES:\n\n" in ctx or not ctx.strip():
        pass
    system = ("You answer questions about a software project using ONLY its knowledge graph "
              "(nodes = entities, edges = relationships). Be concrete; cite node names. "
              "If the graph lacks the info, say so.")
    user = f"KNOWLEDGE GRAPH:\n{ctx[:8000]}\n\nQUESTION: {body.query}\n\nAnswer:"
    answer = await llm_client.complete(system_prompt=system, user_prompt=user, temperature=0.2)
    return {"answer": answer}
