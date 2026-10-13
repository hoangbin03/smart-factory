import asyncio
import json
import structlog
from typing import Dict, Any
from sqlalchemy import text
from app.core.database import AsyncSessionLocal
from app.core.llm_client import llm_config_context
from app.core.nats_client import nats_client
from app.agents.base_agent import BaseAgent, AgentTaskInput, AgentTaskOutput
from app.agents.architect_agent import ArchitectAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.developer_agent import DeveloperAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.qa_agent import QAAgent
from app.agents.devops_agent import DevOpsAgent
from app.agents.nexus_agent import NexusAgent

logger = structlog.get_logger()


class AgentRunner:
    """
    Subscribes to NATS for task execution commands from the Orchestrator,
    resolves the appropriate agent, executes it, and publishes the result.
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._register_agents()
        self._sub = None

    def _register_agents(self):
        # Register the 6 core agents
        for agent_class in [
            ArchitectAgent,
            PlannerAgent,
            DeveloperAgent,
            ReviewerAgent,
            QAAgent,
            DevOpsAgent,
            NexusAgent,
        ]:
            agent = agent_class()
            self._agents[agent.agent_id] = agent
        logger.info("Registered agents", count=len(self._agents), agents=list(self._agents.keys()))

    async def start(self):
        """Start listening for agent execution requests."""
        import json

        async def _message_handler(msg):
            try:
                data = json.loads(msg.data.decode())
                await self._handle_task(data)
            except Exception as e:
                logger.error("Error handling NATS message", error=str(e))

        # Subscribe to runtime.agent.execute
        self._sub = await nats_client.subscribe("runtime.agent.execute", _message_handler)
        logger.info("AgentRunner started listening on 'runtime.agent.execute'")

    async def stop(self):
        if self._sub:
            await self._sub.unsubscribe()
            logger.info("AgentRunner stopped")

    async def _handle_task(self, payload: Dict[str, Any]):
        """Execute task and return result to orchestrator."""
        payload = self._unwrap_nest_payload(payload)
        task_id = payload.get("taskId")
        workflow_id = payload.get("workflowId")
        agent_id = payload.get("agentId")
        goal = payload.get("goal")
        context = payload.get("context", {})
        constraints = payload.get("constraints", {})

        logger.info(
            "Received task execution request",
            task_id=task_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
        )

        agent = self._agents.get(agent_id)
        if not agent:
            logger.error("Agent not found", agent_id=agent_id)
            await self._publish_result(
                task_id=task_id,
                workflow_id=workflow_id,
                agent_id=agent_id,
                success=False,
                summary=f"Agent '{agent_id}' not found in NeMo runtime.",
            )
            return

        # DATA FLOW: hand this agent the outputs of every upstream task in the
        # workflow (architecture, plan, code, review, ...) so agents build on
        # each other instead of each running blind.
        upstream = await self._load_upstream_context(workflow_id)
        if upstream:
            context = {**context, "upstream": upstream}

        # SKILLS & TEMPLATES: load the reusable instruction blocks assigned to
        # this agent. Skills (behavioural) are injected into every prompt;
        # templates (product blueprints) drive what/how the developer builds.
        skills_prompt, templates = await self._load_agent_capabilities(agent_id)
        if skills_prompt:
            context = {**context, "skills": skills_prompt}
        if templates:
            context = {**context, "templates": templates}

        # Workspace to operate on: the project's shared workspace when this
        # workflow belongs to a project, else the workflow's own workspace.
        workspace_id = payload.get("workspaceId") or workflow_id

        task_input = AgentTaskInput(
            workflow_id=workflow_id,
            task_id=task_id,
            goal=goal,
            context=context,
            constraints=constraints,
            workspace_id=workspace_id,
        )

        # Run the agent in the background to not block NATS message processing
        asyncio.create_task(self._execute_and_publish(agent, task_input))

    def _unwrap_nest_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """NestJS ClientProxy wraps NATS event payloads in a data envelope."""
        if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
            return payload["data"]
        return payload

    async def _execute_and_publish(self, agent: BaseAgent, task: AgentTaskInput):
        """Execute agent and publish the result back to orchestrator."""
        import time
        from app.core.llm_client import usage_context
        from app.core.metrics import AGENT_EXECUTIONS, AGENT_DURATION, AGENT_TOKENS, AGENT_REWORKS

        from app.core.memory import memory_client

        start = time.monotonic()
        try:
            # IMPORT: if this workflow pulls an existing codebase (git), make sure
            # it's cloned into the workspace before the first agent works on it.
            await self._ensure_repo_imported(task)

            ai_config = await self._load_agent_ai_config(agent.agent_id)
            # carry the agent's skills into the LLM context so every llm_client
            # call is prefixed with the skill instructions
            if isinstance(task.context, dict) and task.context.get("skills"):
                ai_config = {**ai_config, "skills_prompt": task.context["skills"]}

            # MEMORY (RAG): retrieve knowledge relevant to this goal from past
            # work and inject it into both the LLM system prompt and the task
            # context (so the NAT ReAct agents can use it too).
            memory = await memory_client.retrieve(task.goal, task.workflow_id)
            if memory:
                ai_config = {**ai_config, "memory_prompt": memory}
                if isinstance(task.context, dict):
                    task.context = {**task.context, "memory": memory}

            # accumulate token usage across every LLM call this agent makes
            with usage_context() as usage, llm_config_context(ai_config):
                output: AgentTaskOutput = await agent.execute(task)

            # persist what this agent produced so future tasks can build on it
            if output.success:
                await memory_client.remember(
                    memory_client.summarize_output(output),
                    workflow_id=task.workflow_id,
                    agent_id=agent.agent_id,
                    goal=task.goal,
                )

            duration = time.monotonic() - start

            # observability
            AGENT_DURATION.labels(agent.agent_id).observe(duration)
            AGENT_EXECUTIONS.labels(agent.agent_id, "success" if output.success else "failure").inc()
            AGENT_TOKENS.labels(agent.agent_id, "prompt").inc(usage["prompt_tokens"])
            AGENT_TOKENS.labels(agent.agent_id, "completion").inc(usage["completion_tokens"])
            if (output.metrics or {}).get("needsRework"):
                AGENT_REWORKS.labels(agent.agent_id).inc()

            # Convert output to dict, enriched with cost + timing
            artifacts = [
                {
                    "artifactType": a.artifact_type,
                    "name": a.name,
                    "content": a.content,
                    "metadata": a.metadata,
                }
                for a in output.artifacts
            ]
            metrics = dict(output.metrics or {})
            metrics["tokens"] = usage
            metrics["duration_seconds"] = round(duration, 2)

            await self._publish_result(
                task_id=task.task_id,
                workflow_id=task.workflow_id,
                agent_id=agent.agent_id,
                success=output.success,
                summary=output.summary,
                output={
                    "artifacts": artifacts,
                    "metrics": metrics,
                    "nextAction": output.next_action,
                },
            )

        except Exception as e:
            AGENT_EXECUTIONS.labels(agent.agent_id, "error").inc()
            logger.error("Agent execution crashed", error=str(e), exc_info=True)
            await self._publish_result(
                task_id=task.task_id,
                workflow_id=task.workflow_id,
                agent_id=agent.agent_id,
                success=False,
                summary=f"Agent crashed: {str(e)}",
            )


    async def _ensure_repo_imported(self, task: AgentTaskInput) -> None:
        """
        If the workflow declares a git repo to work on (config.repoImport = {type:'git', url, ...})
        and the workspace is still empty, clone it once so agents operate on the real code.
        Best-effort: never blocks execution if the clone fails.
        """
        try:
            context = task.context if isinstance(task.context, dict) else {}
            cfg = context.get("workflowConfig") if isinstance(context.get("workflowConfig"), dict) else {}
            repo = cfg.get("repoImport") if isinstance(cfg.get("repoImport"), dict) else None
            if not repo or repo.get("type") != "git" or not repo.get("url"):
                return
            from app.workspace import Workspace
            ws = Workspace(task.workspace_id or task.workflow_id).ensure()
            if not ws.is_empty():
                return  # already imported (or an agent already produced files)
            logger.info("Importing repo into workspace", workspace_id=task.workspace_id, url=repo.get("url"))
            result = await ws.import_from_git(repo.get("url"), repo.get("branch", ""), repo.get("token", ""))
            logger.info("Repo import finished", workspace_id=task.workspace_id,
                        ok=result.get("ok"), files=result.get("files"))
        except Exception as exc:  # noqa: BLE001 — import is best-effort
            logger.warning("Repo import failed", workflow_id=task.workflow_id, error=str(exc))

    async def _load_upstream_context(self, workflow_id: str) -> Dict[str, Any]:
        """Collect completed upstream task outputs for a workflow, keyed by agent."""
        upstream: Dict[str, Any] = {}
        if not workflow_id:
            return upstream
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    text(
                        "SELECT agent_id, output FROM tasks "
                        "WHERE workflow_id = :wf AND status = 'COMPLETED' "
                        'ORDER BY "order" ASC'
                    ),
                    {"wf": workflow_id},
                )
                for row in result.mappings().all():
                    output = row.get("output")
                    if isinstance(output, str):
                        output = json.loads(output)
                    artifacts = (output or {}).get("artifacts", []) if isinstance(output, dict) else []
                    texts = []
                    for artifact in artifacts:
                        name = artifact.get("name", "artifact")
                        content = artifact.get("content", "")
                        if content:
                            texts.append(f"### {name}\n{str(content)[:4000]}")
                    if texts:
                        upstream[row["agent_id"]] = "\n\n".join(texts)[:8000]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load upstream context", workflow_id=workflow_id, error=str(exc))
        return upstream

    async def _load_agent_capabilities(self, agent_id: str) -> tuple[str, list]:
        """
        Load the skills/templates assigned to this agent (config.skills = [slug...]).
        Returns (skills_prompt, templates) where:
          - skills_prompt: combined instructions of ALL assigned entries, injected into prompts
          - templates: list of {name, instructions} for kind='template' (product blueprints)
        """
        if not agent_id:
            return "", []
        try:
            async with AsyncSessionLocal() as session:
                row = (await session.execute(
                    text("SELECT config FROM agents WHERE agent_id = :aid"),
                    {"aid": agent_id},
                )).mappings().first()
                config = row.get("config") if row else None
                if isinstance(config, str):
                    config = json.loads(config)
                slugs = (config or {}).get("skills") if isinstance(config, dict) else None
                if not slugs or not isinstance(slugs, list):
                    return "", []

                result = await session.execute(
                    text(
                        "SELECT name, instructions, kind FROM skills "
                        "WHERE slug = ANY(:slugs) AND is_active = TRUE"
                    ),
                    {"slugs": [str(s) for s in slugs]},
                )
                rows = result.mappings().all()
                blocks = [f"[{r['kind'].title()}: {r['name']}] {r['instructions']}" for r in rows]
                templates = [
                    {"name": r["name"], "instructions": r["instructions"]}
                    for r in rows if str(r["kind"]) == "template"
                ]
                prompt = (
                    "You have been equipped with the following skills/templates. Apply them:\n"
                    + "\n".join(blocks)
                ) if blocks else ""
                return prompt, templates
        except Exception as exc:  # noqa: BLE001 — capabilities are best-effort, never block execution
            logger.warning("Failed to load agent capabilities", agent_id=agent_id, error=str(exc))
            return "", []

    async def _load_agent_ai_config(self, agent_id: str) -> Dict[str, Any]:
        """Load per-agent LLM settings from agents.config.ai."""
        try:
            async with AsyncSessionLocal() as session:
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

    async def _publish_result(
        self,
        task_id: str,
        workflow_id: str,
        agent_id: str,
        success: bool,
        summary: str,
        output: Dict[str, Any] = None,
    ):
        """Send the result back to the orchestrator via NATS."""
        import uuid
        from datetime import datetime, timezone

        payload = {
            "eventId": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "agent-runtime-service",
            "taskId": task_id,
            "workflowId": workflow_id,
            "agentId": agent_id,
            "success": success,
            "summary": summary,
            "output": output or {},
        }

        await nats_client.publish("runtime.agent.result", payload)
        logger.info(
            "Published agent result",
            task_id=task_id,
            agent_id=agent_id,
            success=success,
        )
