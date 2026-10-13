"""Nexus — REST chat endpoint (non-WebSocket fallback)."""
import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.agent_config import load_agent_ai_config
from app.core.database import get_session
from app.core.llm_client import llm_config_context, llm_client
from app.monitor.event_aggregator import aggregator
from app.monitor.factory_state import load_nexus_snapshot, load_factory_state
from app.api.v1.endpoints.skills import ensure_skills_table, _slugify
from app.api.v1.endpoints.projects import (
    create_project as _create_project, ProjectCreate, ensure_project_tables, _kg_context,
)

router = APIRouter()

# Lets Nexus turn a natural-language request into a real skill/template.
SKILL_CREATION_ADDON = """

TOOL — CREATE SKILL/TEMPLATE:
You can create reusable skills or templates for the factory's agents. If (and only if) the user
asks you to create/add/make a skill or template, reply with ONLY a single JSON object, no prose and
no markdown fences, in this exact shape:
{"action":"create_skill","skill":{"name":"...","kind":"skill","category":"...","description":"...","instructions":"...","tags":["..."]}}
- kind must be "skill" or "template".
- instructions must be concrete, actionable guidance the agent will follow.
For every other kind of request, answer normally in prose."""


# Lets Nexus turn a natural-language request into a real workflow with tasks
# assigned to the right agents (created as a PENDING draft for the user to start).
WORKFLOW_CREATION_ADDON = """

TOOL — DELEGATE WORK (CREATE WORKFLOW):
When the user asks you to BUILD, IMPLEMENT, FIX, REFACTOR, or otherwise DO a software task
(optionally on an existing repo), you act as the dispatcher: design the work and assign it to
the right agents. Reply with ONLY a single JSON object, no prose and no markdown fences, in this exact shape:
{"action":"create_workflow","workflow":{
  "name":"short workflow name",
  "goal":"one-sentence goal",
  "project":"exact existing project name to run this work ON (optional)",
  "repo":{"type":"git","url":"https://...","branch":""},
  "tasks":[{"agent":"developer_agent","name":"Fix login bug","goal":"..."}]
}}
- Include "project" when the user wants work done on an EXISTING project/codebase they already have
  (the run then uses that project's shared workspace + knowledge graph). See the FACTORY STATE for names.
- Include "repo" ONLY if the user gave a git URL to pull/continue/fix and there is no project; otherwise omit it.
- "tasks" is an ORDERED list. Pick only the agents that FIT the request from:
  architect_agent, planner_agent, developer_agent, reviewer_agent, qa_agent, devops_agent.
  (e.g. a small bug fix might be just developer_agent then reviewer_agent; a new product uses the full set.)
- Each task needs a concrete, specific goal for that agent.
For every other kind of request (questions, status, chat), answer normally in prose."""

VALID_AGENTS = {
    "architect_agent", "planner_agent", "developer_agent",
    "reviewer_agent", "qa_agent", "devops_agent",
}

# Lets Nexus create a PROJECT (codebase container) from git / empty on request.
PROJECT_CREATION_ADDON = """

TOOL — CREATE PROJECT:
When the user asks you to CREATE, IMPORT or CLONE a PROJECT / codebase (e.g. "tạo project từ repo X",
"clone repo ... thành dự án", "tạo dự án mới trống"), reply with ONLY this JSON, no prose, no fences:
{"action":"create_project","project":{"name":"...","description":"...","source_type":"git|empty","repo_url":"https://... only if git","branch":""}}
Use source_type "git" with repo_url when a git URL is given; otherwise "empty". This is DIFFERENT from
create_workflow: a project is a persistent codebase you can build a knowledge graph on, not a task pipeline."""


class ChatMessage(BaseModel):
    message: str
    history: List[Dict[str, str]] = []


async def _maybe_create_skill(reply: str) -> Optional[Dict[str, Any]]:
    """If the model emitted a create_skill action, persist the skill and return it."""
    match = re.search(r"\{.*\}", reply.strip(), re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("action") != "create_skill":
        return None

    skill = payload.get("skill") or {}
    name = str(skill.get("name") or "").strip()
    instructions = str(skill.get("instructions") or "").strip()
    if not name or not instructions:
        return None

    await ensure_skills_table()
    slug = _slugify(name)
    async with get_session() as session:
        if (await session.execute(text("SELECT 1 FROM skills WHERE slug = :s"), {"s": slug})).first():
            n = (await session.execute(text("SELECT COUNT(*) FROM skills"))).scalar()
            slug = f"{slug}-{n}"
        row = (await session.execute(
            text(
                "INSERT INTO skills (slug, name, description, category, kind, instructions, tags) "
                "VALUES (:slug, :name, :description, :category, :kind, :instructions, :tags) RETURNING *"
            ),
            {
                "slug": slug, "name": name,
                "description": str(skill.get("description") or ""),
                "category": str(skill.get("category") or "general"),
                "kind": "template" if str(skill.get("kind")) == "template" else "skill",
                "instructions": instructions,
                "tags": [str(t) for t in (skill.get("tags") or [])],
            },
        )).mappings().first()
        await session.commit()
    return dict(row)


async def _maybe_create_workflow(reply: str) -> Optional[Dict[str, Any]]:
    """If Nexus emitted a create_workflow action, create a PENDING workflow + tasks."""
    match = re.search(r"\{.*\}", reply.strip(), re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("action") != "create_workflow":
        return None

    wf = payload.get("workflow") or {}
    name = str(wf.get("name") or "").strip() or "Nexus-assigned work"
    goal = str(wf.get("goal") or "").strip()
    tasks_in = wf.get("tasks")
    if not goal or not isinstance(tasks_in, list) or not tasks_in:
        return None

    # Build the config (carry repo import instructions if provided)
    config: Dict[str, Any] = {}
    repo = wf.get("repo")
    if isinstance(repo, dict) and repo.get("url"):
        config["repoImport"] = {
            "type": "git",
            "url": str(repo.get("url")).strip(),
            "branch": str(repo.get("branch") or "").strip(),
        }

    # Normalise tasks — keep only valid agents, in the given order
    tasks: List[Dict[str, Any]] = []
    for item in tasks_in:
        if not isinstance(item, dict):
            continue
        agent = str(item.get("agent") or "").strip()
        if agent not in VALID_AGENTS:
            continue
        tasks.append({
            "agent": agent,
            "name": str(item.get("name") or agent.replace("_agent", "").title()).strip()[:200],
            "goal": str(item.get("goal") or goal).strip(),
        })
    if not tasks:
        return None

    metadata = {"createdByNexus": True}
    async with get_session() as session:
        # Attach to an existing project (by name) so the run uses its shared workspace.
        project_id = None
        proj_name = str(wf.get("project") or "").strip()
        if proj_name:
            await ensure_project_tables()
            pr = (await session.execute(
                text("SELECT id FROM projects WHERE lower(name) = lower(:n) ORDER BY created_at DESC LIMIT 1"),
                {"n": proj_name},
            )).first()
            if pr:
                project_id = str(pr[0])
                config.pop("repoImport", None)  # project already has the code

        row = (await session.execute(
            text(
                "INSERT INTO workflows (name, status, goal, config, metadata, project_id) "
                "VALUES (:name, 'PENDING', :goal, CAST(:config AS jsonb), CAST(:metadata AS jsonb), :pid) "
                "RETURNING id"
            ),
            {"name": name, "goal": goal, "config": json.dumps(config),
             "metadata": json.dumps(metadata), "pid": project_id},
        )).mappings().first()
        workflow_id = str(row["id"])

        for order, t in enumerate(tasks):
            task_input = {
                "workflowName": name,
                "workflowGoal": goal,
                "workflowConfig": config,
                "pipelineStep": t["name"],
            }
            await session.execute(
                text(
                    "INSERT INTO tasks (workflow_id, name, status, agent_id, goal, input, \"order\") "
                    "VALUES (:wid, :name, 'PENDING', :agent, :goal, CAST(:input AS jsonb), :order)"
                ),
                {"wid": workflow_id, "name": t["name"], "agent": t["agent"],
                 "goal": t["goal"], "input": json.dumps(task_input), "order": order},
            )
        await session.commit()

    return {"id": workflow_id, "name": name, "goal": goal,
            "tasks": tasks, "repoImport": config.get("repoImport")}


async def _maybe_create_project(reply: str) -> Optional[Dict[str, Any]]:
    """If Nexus emitted a create_project action, create the project (clone if git)."""
    match = re.search(r"\{.*\}", reply.strip(), re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or payload.get("action") != "create_project":
        return None
    p = payload.get("project") or {}
    name = str(p.get("name") or "").strip()
    if not name:
        return None
    st = p.get("source_type") if p.get("source_type") in ("git", "empty", "folder") else "empty"
    body = ProjectCreate(
        name=name, description=str(p.get("description") or ""), source_type=st,
        repo_url=str(p.get("repo_url") or ""), branch=str(p.get("branch") or ""),
    )
    return await _create_project(body)


async def _project_kg_context(message: str) -> str:
    """If the message names a project that has a knowledge graph, inject its KG so
    Nexus can 'understand' the project through the graph."""
    try:
        await ensure_project_tables()
        async with get_session() as session:
            rows = (await session.execute(
                text("SELECT id, name FROM projects WHERE kg_status = 'READY'")
            )).mappings().all()
        low = message.lower()
        for r in rows:
            nm = str(r["name"] or "").strip()
            if nm and len(nm) >= 3 and nm.lower() in low:
                ctx = await _kg_context(str(r["id"]))
                return f"\n\nKNOWLEDGE GRAPH of project '{nm}' (use it to answer accurately):\n{ctx[:4000]}"
    except Exception:  # noqa: BLE001
        return ""
    return ""


@router.post("/")
async def chat(body: ChatMessage):
    ctx = await load_nexus_snapshot(aggregator.snapshot())
    db_state = await load_factory_state()
    context_str = json.dumps(
        {"live_events": ctx, "database_state": db_state},
        default=str,
        indent=2,
    )[:6000]

    kg_context = await _project_kg_context(body.message)

    system_prompt = f"""Bạn là Nexus — Master Intelligence Agent của Smart Software Factory.
Bạn theo dõi TẤT CẢ hoạt động: workflows, agents, tasks, projects.
Trả lời bằng tiếng Việt nếu người dùng dùng tiếng Việt.

FACTORY STATE (realtime snapshot):
{context_str}{kg_context}{SKILL_CREATION_ADDON}{WORKFLOW_CREATION_ADDON}{PROJECT_CREATION_ADDON}"""

    history_text = "\n".join([
        f"{m['role'].upper()}: {m['content']}"
        for m in (body.history or [])[-6:]
    ])
    user_prompt = f"{history_text}\nUSER: {body.message}"

    ai_config = await load_agent_ai_config("nexus_agent")
    with llm_config_context(ai_config):
        reply = await llm_client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.3,
        )

    # If Nexus decided to create a skill, execute it and confirm in plain language.
    created = await _maybe_create_skill(reply)
    if created:
        return {
            "reply": (
                f"✅ Đã tạo {created['kind']} **{created['name']}** (slug: `{created['slug']}`).\n"
                f"Bạn có thể gán nó cho agent tại trang **Templates & Skills**."
            ),
            "action": "skill_created",
            "skill": created,
        }

    # If Nexus decided to create a project (codebase container), create it now.
    project = await _maybe_create_project(reply)
    if project:
        pid = str(project.get("id"))
        src = project.get("source_type")
        imp = project.get("import") or {}
        extra = ""
        if src == "git":
            extra = ("\n📥 Đã clone code về workspace." if imp.get("ok")
                     else "\n⚠️ Clone chưa thành công — kiểm tra URL/branch/token.")
        return {
            "reply": (
                f"✅ Đã tạo project **{project.get('name')}** (nguồn: {src}).{extra}\n\n"
                f"Mở trang **Projects** để bấm **Generate graph** dựng knowledge graph "
                f"và khám phá mối liên hệ giữa các thực thể."
            ),
            "action": "project_created",
            "project": {"id": pid, "name": project.get("name")},
        }

    # If Nexus decided to delegate work, create a draft workflow with assigned agents.
    workflow = await _maybe_create_workflow(reply)
    if workflow:
        steps = "\n".join(
            f"{i+1}. **{t['name']}** → `{t['agent']}`" for i, t in enumerate(workflow["tasks"])
        )
        repo_line = (
            f"\n📥 Sẽ pull code từ: `{workflow['repoImport']['url']}`"
            if workflow.get("repoImport") else ""
        )
        return {
            "reply": (
                f"✅ Đã tạo workflow nháp **{workflow['name']}** (trạng thái PENDING).{repo_line}\n\n"
                f"Các bước em đã giao cho agent:\n{steps}\n\n"
                f"Mở trang **Workflows** rồi bấm **Start** để nhà máy bắt đầu."
            ),
            "action": "workflow_created",
            "workflow": workflow,
        }

    return {"reply": reply}
