"""
Base Tool Contract
All tools available to agents must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import structlog

logger = structlog.get_logger()


@dataclass
class ToolInput:
    """Standardized tool input."""
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolOutput:
    """Standardized tool output."""
    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseTool(ABC):
    """
    Base class for all Factory Platform tools.
    Tools are the only way agents can interact with the external world.
    """

    tool_id: str = "base_tool"
    description: str = "Base tool"
    version: str = "1.0.0"

    def __init__(self):
        self.logger = structlog.get_logger(tool=self.tool_id)

    async def execute(self, input: ToolInput) -> ToolOutput:
        """Execute the tool with the given input."""
        self.logger.info("Tool executing", action=input.action)
        try:
            result = await self._execute(input)
            return result
        except Exception as e:
            self.logger.error("Tool execution failed", error=str(e))
            return ToolOutput(success=False, error=str(e))

    @abstractmethod
    async def _execute(self, input: ToolInput) -> ToolOutput:
        """Internal implementation — override this."""
        ...

    def describe(self) -> dict[str, Any]:
        return {
            "tool_id": self.tool_id,
            "description": self.description,
            "version": self.version,
        }
