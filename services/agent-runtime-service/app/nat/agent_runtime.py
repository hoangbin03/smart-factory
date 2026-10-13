"""
Generic NVIDIA NeMo Agent Toolkit (NAT) ReAct runner for the non-developer agents.

Lets reviewer / QA / architect / planner actually REASON AND CALL TOOLS
(read files, list files, run commands) against the workflow workspace instead of
making a single blind LLM call. E.g. the reviewer can `factory_run_command` to
lint the real code, and QA can run checks itself.

`analyze()` is the drop-in each agent uses: it runs through NAT when the agent's
role is enabled via settings.USE_NAT_AGENTS, and otherwise (or on any failure)
falls back to a plain llm_client.complete() call — so the pipeline never breaks.
"""
from typing import Any, Optional

import structlog

from app.core.config import settings
from app.core.llm_client import llm_client, current_prompt_injections

logger = structlog.get_logger()

_NAT_READY = False

# Read-only + run tools: safe for analysis agents (no factory_write_file).
ANALYST_TOOL_NAMES = ["factory_read_file", "factory_list_files", "factory_run_command"]


def _ensure_nat_registrations() -> None:
    global _NAT_READY
    if _NAT_READY:
        return
    import nat.plugins.langchain.llm  # noqa: F401
    import nat.plugins.langchain.tool_wrapper  # noqa: F401
    import nat.plugins.langchain.agent.react_agent.register  # noqa: F401
    import app.nat.functions  # noqa: F401
    _NAT_READY = True


def nat_roles() -> set[str]:
    """Roles enabled to run through NAT, from settings.USE_NAT_AGENTS (comma list)."""
    raw = settings.USE_NAT_AGENTS or ""
    return {r.strip().lower() for r in raw.split(",") if r.strip()}


async def run_nat_agent(
    workflow_id: str,
    system_prompt: str,
    user_prompt: str,
    tool_names: Optional[list[str]] = None,
) -> str:
    """Run a ReAct agent with workspace tools and return its final text answer.
    Raises on any failure so the caller can fall back to a plain LLM call.
    """
    _ensure_nat_registrations()

    from nat.builder.workflow_builder import WorkflowBuilder
    from nat.llm.openai_llm import OpenAIModelConfig
    from nat.plugins.langchain.agent.react_agent.register import ReActAgentWorkflowConfig
    from app.nat.functions import ReadFileConfig, ListFilesConfig, RunCommandConfig

    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured for NAT agent")

    tools = tool_names or ANALYST_TOOL_NAMES

    async with WorkflowBuilder() as wb:
        await wb.add_llm("factory_llm", OpenAIModelConfig(
            model_name=settings.OPENROUTER_MODEL or settings.DEFAULT_MODEL,
            api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=settings.TEMPERATURE,
        ))
        await wb.add_function("factory_read_file", ReadFileConfig(workflow_id=workflow_id))
        await wb.add_function("factory_list_files", ListFilesConfig(workflow_id=workflow_id))
        await wb.add_function("factory_run_command", RunCommandConfig(workflow_id=workflow_id))
        await wb.set_workflow(ReActAgentWorkflowConfig(
            llm_name="factory_llm",
            tool_names=tools,
            verbose=True,
            max_tool_calls=settings.NAT_MAX_TOOL_CALLS,
            use_native_tool_calling=True,
        ))
        workflow = await wb.build()

        # keep the same skills/memory the plain LLM path would have injected
        injections = current_prompt_injections()
        prefix = f"{injections}\n\n" if injections else ""
        prompt = (
            f"{prefix}{system_prompt}\n\n{user_prompt}\n\n"
            "You MAY use the tools to inspect the workspace (list files, read each "
            "file at most once, run checks). Then STOP calling tools and write your "
            "COMPLETE result as the Final Answer. Do NOT narrate tool calls in the "
            "final answer — it must be the full deliverable itself."
        )
        async with workflow.run(prompt) as runner:
            answer = await runner.result(to_type=str)

    return str(answer or "")


def _looks_unfinished(text: str) -> bool:
    """True if a NAT answer is really a leaked ReAct trace / stub, not a deliverable.

    gpt-4o-mini sometimes returns an intermediate 'Calling <tool>...' thought as
    the final answer when the ReAct loop terminates early. Such outputs are
    useless, so we reject them and fall back to a direct LLM call.
    """
    t = (text or "").strip()
    if len(t) < 160:
        return True
    low = t.lower()
    trace_starts = ("calling ", "invoking ", "i will call", "i'll call",
                    "let me ", "thought:", "action:")
    return low.startswith(trace_starts)


async def analyze(
    role: str,
    workflow_id: str,
    system_prompt: str,
    user_prompt: str,
    tool_names: Optional[list[str]] = None,
) -> str:
    """NAT ReAct when the role is enabled, else a plain LLM call. Never raises."""
    if role.lower() in nat_roles():
        try:
            out = await run_nat_agent(workflow_id, system_prompt, user_prompt, tool_names)
            if out and not _looks_unfinished(out):
                logger.info("NAT agent produced analysis", role=role, workflow_id=workflow_id,
                            chars=len(out))
                return out
            logger.warning("NAT output unusable (unfinished/empty), falling back to direct LLM",
                           role=role, preview=(out or "")[:80])
        except Exception as exc:  # noqa: BLE001 — degrade gracefully to direct LLM
            logger.warning("NAT agent failed, falling back to direct LLM", role=role, error=str(exc))
    return await llm_client.complete(system_prompt=system_prompt, user_prompt=user_prompt)
