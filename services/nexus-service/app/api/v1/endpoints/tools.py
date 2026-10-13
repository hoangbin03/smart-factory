"""
Nexus — Tool Catalog endpoint.

Describes the tools the Factory runtime exposes to agents. The `active` tools are
registered as NVIDIA NeMo Agent Toolkit (NAT) functions and are called by the NAT
ReAct agent that powers the Developer Agent. Statuses:
  - active  : a real, wired tool (filesystem/terminal/git/verify) that runs on disk
  - builtin : LLM-native capability (no external side effects)
  - planned : declared in the roadmap, not yet implemented
The per-agent tool assignment is stored on the `agents.tools` column and edited
via PATCH /agents/{id}.
"""
from fastapi import APIRouter

router = APIRouter()

TOOL_CATALOG = [
    {
        "tool_id": "filesystem_tool",
        "name": "Filesystem",
        "category": "workspace",
        "status": "active",
        "description": "Sandboxed read/write access confined to the per-workflow workspace. No path traversal.",
    },
    {
        "tool_id": "terminal_tool",
        "name": "Terminal",
        "category": "execution",
        "status": "active",
        "description": "Runs shell commands (install, build, lint, tests) inside the workspace with a timeout and captured output.",
    },
    {
        "tool_id": "git_tool",
        "name": "Git",
        "category": "vcs",
        "status": "active",
        "description": "Real version control in the workspace: init, stage, commit, log.",
    },
    {
        "tool_id": "code_analysis_tool",
        "name": "Code Analysis",
        "category": "quality",
        "status": "active",
        "description": "Reads the real code from the workspace for review (correctness, security, quality).",
    },
    {
        "tool_id": "test_runner_tool",
        "name": "Test Runner",
        "category": "quality",
        "status": "active",
        "description": "Runs real verification on delivered files (node --check, py_compile, JSON/HTML validation, pytest/npm test).",
    },
    {
        "tool_id": "search_tool",
        "name": "Search",
        "category": "knowledge",
        "status": "builtin",
        "description": "Retrieves context from the knowledge base / web to ground the agent.",
    },
    {
        "tool_id": "documentation_tool",
        "name": "Documentation",
        "category": "knowledge",
        "status": "builtin",
        "description": "Produces and consults design/architecture documentation.",
    },
    {
        "tool_id": "planning_tool",
        "name": "Planning",
        "category": "planning",
        "status": "builtin",
        "description": "Decomposes goals into epics, stories, and tasks.",
    },
    {
        "tool_id": "docker_tool",
        "name": "Docker",
        "category": "devops",
        "status": "planned",
        "description": "Build and run container images for delivered projects. (Roadmap)",
    },
    {
        "tool_id": "kubernetes_tool",
        "name": "Kubernetes",
        "category": "devops",
        "status": "planned",
        "description": "Deploy manifests to a cluster and manage rollouts. (Roadmap)",
    },
]


@router.get("/")
async def list_tools():
    return {"data": TOOL_CATALOG, "total": len(TOOL_CATALOG)}
