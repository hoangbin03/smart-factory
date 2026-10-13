"""
Run the Developer Agent through NVIDIA NeMo Agent Toolkit (NAT).

Builds a NAT workflow (OpenRouter LLM + Factory tool functions + prebuilt
ReAct agent) per task and lets the agent actually reason and call tools to
write and verify code in the workflow's isolated Workspace.
"""
import re
from typing import Any

import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Importing these registers the LLM client conversion, the tool wrapper, the
# ReAct agent, and our Factory tool functions with NAT's global registry.
_NAT_READY = False


def _ensure_nat_registrations() -> None:
    global _NAT_READY
    if _NAT_READY:
        return
    import nat.plugins.langchain.llm  # noqa: F401  OpenAI->LangChain LLM client
    import nat.plugins.langchain.tool_wrapper  # noqa: F401  function->LangChain tool
    import nat.plugins.langchain.agent.react_agent.register  # noqa: F401  react_agent
    import app.nat.functions  # noqa: F401  factory tool functions
    _NAT_READY = True


def _missing_referenced_assets(files: list[dict[str, Any]]) -> set[str]:
    """Return local assets referenced by index.html (script src / link href) that were not written."""
    by_name = {f["name"].lower().lstrip("./"): f for f in files}
    index = next((f for f in files if f["name"].lower() == "index.html"), None)
    if not index:
        return set()  # non-frontend package — nothing to check here
    html = index["content"]
    refs = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', html, flags=re.IGNORECASE)
    missing: set[str] = set()
    for ref in refs:
        if ref.startswith(("http://", "https://", "//", "data:", "#", "mailto:")):
            continue
        target = ref.split("?")[0].split("#")[0].lstrip("./").lower()
        if not target or not (target.endswith(".js") or target.endswith(".css")):
            continue
        if target not in by_name:
            missing.add(ref)
    return missing


def _build_goal_prompt(
    goal: str,
    upstream: dict[str, Any] | None,
    rework: Any,
    skills: Any = None,
    templates: list | None = None,
    memory: Any = None,
    existing_project: bool = False,
) -> str:
    if existing_project:
        parts = [
            "You are the Developer Agent in a software factory, working on an EXISTING "
            "codebase that is ALREADY PRESENT in the workspace.",
            "",
            f"GOAL: {goal}",
            "",
            "Rules:",
            "- FIRST call factory_list_files, then factory_read_file on the relevant files "
            "to understand the current code.",
            "- MODIFY the existing files with factory_write_file to achieve the goal. Do NOT "
            "rewrite the whole project or delete unrelated files.",
            "- Use factory_run_command to verify your changes (build/lint/test) when possible.",
            "- Keep going until the change is complete and verified, then give a short Final Answer.",
        ]
        if rework:
            parts.append(f"\nThis is a REWORK. Fix these issues from the previous review/QA:\n{str(rework)[:1200]}")
        if memory:
            parts.append(f"\n{str(memory)[:1200]}")
        return "\n".join(parts)
    if templates:
        blueprint = "\n\n".join(
            f"— {t.get('name')}:\n{t.get('instructions')}" for t in templates if isinstance(t, dict)
        )
        structure_rule = (
            "- Follow the PROJECT TEMPLATE exactly (its stack, files and structure). "
            "Create as many files as the template needs — do not force a fixed layout."
        )
    else:
        blueprint = ""
        structure_rule = (
            "- Choose the right stack/structure for the goal. For web/game/UI goals, produce a static "
            "frontend (index.html + its local assets, no external network assets)."
        )
    parts = [
        "You are the Developer Agent in a software factory. Build a COMPLETE, runnable product "
        "for the goal below by WRITING FILES to the workspace with the factory_write_file tool.",
        "",
        f"GOAL: {goal}",
    ]
    if blueprint:
        parts.append(f"\nPROJECT TEMPLATE (build to match this):\n{blueprint[:2000]}")
    parts += [
        "",
        "Rules:",
        structure_rule,
        "- Write every file with factory_write_file. Do not just describe code — actually write it.",
        "- After writing, use factory_run_command to verify (e.g. 'node --check script.js') and "
        "factory_list_files to confirm the files exist.",
        "- Keep going until all files are written and verified, then give a short Final Answer.",
    ]
    if upstream:
        arch = upstream.get("architect_agent")
        planner = upstream.get("planner_agent")
        if arch:
            parts.append(f"\nArchitecture to follow:\n{str(arch)[:1500]}")
        if planner:
            parts.append(f"\nPlan to follow:\n{str(planner)[:1000]}")
    if rework:
        parts.append(f"\nThis is a REWORK. Fix these issues from the previous review/QA:\n{str(rework)[:1200]}")
    if skills:
        parts.append(f"\nApply these equipped skills while building:\n{str(skills)[:1500]}")
    if memory:
        parts.append(f"\n{str(memory)[:1500]}")
    return "\n".join(parts)


async def run_nat_developer(
    workflow_id: str,
    goal: str,
    upstream: dict[str, Any] | None = None,
    rework: Any = None,
    skills: Any = None,
    templates: list | None = None,
    memory: Any = None,
    existing_project: bool = False,
) -> dict[str, Any]:
    """
    Execute the developer task via the NAT ReAct agent. Returns a product dict
    ({files, product_type, summary, ...}) read back from the workspace so the
    existing materialize/verify/commit/report pipeline can consume it.
    Raises on any failure so the caller can fall back to direct generation.
    """
    _ensure_nat_registrations()

    from nat.builder.workflow_builder import WorkflowBuilder
    from nat.llm.openai_llm import OpenAIModelConfig
    from nat.plugins.langchain.agent.react_agent.register import ReActAgentWorkflowConfig
    from app.nat.functions import (
        WriteFileConfig, ReadFileConfig, ListFilesConfig, RunCommandConfig, DEVELOPER_TOOL_NAMES,
    )
    from app.workspace import Workspace

    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured for NAT developer")

    async with WorkflowBuilder() as wb:
        await wb.add_llm("factory_llm", OpenAIModelConfig(
            model_name=settings.OPENROUTER_MODEL or settings.DEFAULT_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=settings.TEMPERATURE,
        ))
        await wb.add_function("factory_write_file", WriteFileConfig(workflow_id=workflow_id))
        await wb.add_function("factory_read_file", ReadFileConfig(workflow_id=workflow_id))
        await wb.add_function("factory_list_files", ListFilesConfig(workflow_id=workflow_id))
        await wb.add_function("factory_run_command", RunCommandConfig(workflow_id=workflow_id))
        await wb.set_workflow(ReActAgentWorkflowConfig(
            llm_name="factory_llm",
            tool_names=DEVELOPER_TOOL_NAMES,
            verbose=True,
            max_tool_calls=settings.NAT_MAX_TOOL_CALLS,
            use_native_tool_calling=True,
        ))
        workflow = await wb.build()

        prompt = _build_goal_prompt(goal, upstream, rework, skills, templates, memory, existing_project)
        logger.info("NAT ReAct developer starting", workflow_id=workflow_id)
        async with workflow.run(prompt) as runner:
            answer = await runner.result(to_type=str)

    files = Workspace(workflow_id).snapshot_as_files()
    if not files:
        raise RuntimeError("NAT developer produced no files in the workspace")

    # Quality gate: if the ReAct agent left the product incomplete (e.g. index.html
    # references a script.js it never wrote), reject so the caller falls back to the
    # reliable direct generator. The NeMo run still happened — it just wasn't good enough.
    missing = _missing_referenced_assets(files)
    if missing:
        raise RuntimeError(f"NAT product incomplete — missing referenced files: {', '.join(sorted(missing))}")

    logger.info("NAT ReAct developer finished", workflow_id=workflow_id, files=len(files))
    return {
        "files": files,
        "product_type": "static_frontend" if any(f["name"].lower() == "index.html" for f in files) else "implementation_package",
        "summary": str(answer)[:500] if answer else "Product built by the NeMo ReAct developer agent.",
        "generated_by": "nemo_react_agent",
    }
