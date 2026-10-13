"""
Base Agent Contract
All agents in the NeMo runtime must implement this interface.

Lifecycle: Receive → Understand → Plan → Execute → Validate → Reflect → Report
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
import structlog

logger = structlog.get_logger()


@dataclass
class AgentTaskInput:
    """Standardized agent task input contract."""
    workflow_id: str
    task_id: str
    goal: str
    context: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    # Disk workspace to operate on. For a workflow that belongs to a project this
    # is the PROJECT's id (shared codebase); for a standalone workflow it is the
    # workflow id. Always set by the runner — defaults to workflow_id.
    workspace_id: str = ""

    @property
    def ws(self) -> str:
        """The workspace directory id to operate on (project id, or workflow id)."""
        return self.workspace_id or self.workflow_id


@dataclass
class AgentArtifact:
    """An artifact produced by an agent."""
    artifact_type: str
    name: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentTaskOutput:
    """Standardized agent task output contract."""
    success: bool
    summary: str
    artifacts: list[AgentArtifact] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    next_action: Optional[str] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all Factory Platform agents.

    Enforces the agent contract: no agent-to-agent calls.
    All communication happens through the Factory Orchestrator.
    """

    agent_id: str = "base_agent"
    role: str = "base"
    version: str = "1.0.0"

    def __init__(self):
        self.logger = structlog.get_logger(agent=self.agent_id)
        self._tools: dict[str, Any] = {}

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool for use by this agent."""
        self._tools[name] = tool
        self.logger.info("Tool registered", tool=name)

    def get_tool(self, name: str) -> Any:
        """Get a registered tool by name."""
        if name not in self._tools:
            raise ValueError(f"Tool '{name}' not registered for agent {self.agent_id}")
        return self._tools[name]

    async def execute(self, task: AgentTaskInput) -> AgentTaskOutput:
        """
        Main agent execution lifecycle.
        DO NOT OVERRIDE — override the individual lifecycle methods.
        """
        self.logger.info(
            "Agent execution started",
            workflow_id=task.workflow_id,
            task_id=task.task_id,
            goal=task.goal,
        )

        try:
            # Phase 1: Understand
            understanding = await self.understand(task)

            # Phase 2: Plan
            plan = await self.plan(task, understanding)

            # Phase 3: Execute
            result = await self.run(task, plan)

            # Phase 4: Validate
            is_valid = await self.validate(task, result)
            if not is_valid:
                self.logger.warning("Validation failed, re-running...")
                result = await self.run(task, plan)

            # Phase 5: Reflect
            reflection = await self.reflect(task, result)

            # Phase 6: Report
            output = await self.report(task, result, reflection)

            self.logger.info(
                "Agent execution completed",
                success=output.success,
                artifacts=len(output.artifacts),
            )
            return output

        except Exception as e:
            self.logger.error("Agent execution failed", error=str(e))
            return AgentTaskOutput(
                success=False,
                summary=f"Agent {self.agent_id} failed: {str(e)}",
                error=str(e),
            )

    @abstractmethod
    async def understand(self, task: AgentTaskInput) -> dict[str, Any]:
        """Parse and understand the task goal and context."""
        ...

    @abstractmethod
    async def plan(self, task: AgentTaskInput, understanding: dict[str, Any]) -> list[str]:
        """Create an execution plan (list of steps)."""
        ...

    @abstractmethod
    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        """Execute the plan using tools."""
        ...

    @abstractmethod
    async def validate(self, task: AgentTaskInput, result: dict[str, Any]) -> bool:
        """Validate the execution result."""
        ...

    @abstractmethod
    async def reflect(self, task: AgentTaskInput, result: dict[str, Any]) -> str:
        """Reflect on the execution and summarize learnings."""
        ...

    @abstractmethod
    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        """Generate the final structured output."""
        ...
