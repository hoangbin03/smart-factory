import asyncio
import structlog
from typing import Dict, Any
from app.core.nats_client import nats_client
from app.agents.base_agent import BaseAgent, AgentTaskInput, AgentTaskOutput
from app.agents.architect_agent import ArchitectAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.developer_agent import DeveloperAgent
from app.agents.reviewer_agent import ReviewerAgent
from app.agents.qa_agent import QAAgent
from app.agents.devops_agent import DevOpsAgent

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

        task_input = AgentTaskInput(
            workflow_id=workflow_id,
            task_id=task_id,
            goal=goal,
            context=context,
            constraints=constraints,
        )

        # Run the agent in the background to not block NATS message processing
        asyncio.create_task(self._execute_and_publish(agent, task_input))

    async def _execute_and_publish(self, agent: BaseAgent, task: AgentTaskInput):
        """Execute agent and publish the result back to orchestrator."""
        try:
            output: AgentTaskOutput = await agent.execute(task)

            # Convert output to dict
            artifacts = [
                {
                    "artifactType": a.artifact_type,
                    "name": a.name,
                    "content": a.content,
                    "metadata": a.metadata,
                }
                for a in output.artifacts
            ]

            await self._publish_result(
                task_id=task.task_id,
                workflow_id=task.workflow_id,
                agent_id=agent.agent_id,
                success=output.success,
                summary=output.summary,
                output={
                    "artifacts": artifacts,
                    "metrics": output.metrics,
                    "nextAction": output.next_action,
                },
            )

        except Exception as e:
            logger.error("Agent execution crashed", error=str(e), exc_info=True)
            await self._publish_result(
                task_id=task.task_id,
                workflow_id=task.workflow_id,
                agent_id=agent.agent_id,
                success=False,
                summary=f"Agent crashed: {str(e)}",
            )

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
