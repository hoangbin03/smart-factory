"""
LLM-Powered Base Agent
Adds LLM integration to the base agent lifecycle.
All concrete agents inherit from this.
"""
from typing import Any
from app.agents.base_agent import BaseAgent, AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client


class LLMAgent(BaseAgent):
    """Base agent with LLM-powered lifecycle methods."""

    SYSTEM_PROMPT: str = "You are an AI agent in the Factory Platform."

    async def understand(self, task: AgentTaskInput) -> dict[str, Any]:
        response = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Analyze this task:
Goal: {task.goal}
Context: {task.context}
Constraints: {task.constraints}

Provide a structured understanding of what needs to be done.""",
        )
        return {"understanding": response, "goal": task.goal}

    async def plan(self, task: AgentTaskInput, understanding: dict[str, Any]) -> list[str]:
        response = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create a step-by-step execution plan:
Understanding: {understanding.get('understanding', '')}
Goal: {task.goal}

List exactly the steps needed. Be concise and actionable.""",
        )
        # Parse plan steps
        lines = [l.strip() for l in response.split('\n') if l.strip()]
        steps = [l for l in lines if l and not l.startswith('#')]
        return steps[:10]  # Max 10 steps

    async def validate(self, task: AgentTaskInput, result: dict[str, Any]) -> bool:
        if result.get("error"):
            return False
        return bool(result.get("output"))

    async def reflect(self, task: AgentTaskInput, result: dict[str, Any]) -> str:
        response = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Reflect on this task execution:
Goal: {task.goal}
Result: {str(result)[:500]}

Summarize what was accomplished, what worked well, and any improvements.""",
        )
        return response

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        artifacts = []
        if "output" in result and isinstance(result["output"], str):
            artifacts.append(AgentArtifact(
                artifact_type="text",
                name=f"{self.agent_id}_output",
                content=result["output"],
            ))

        return AgentTaskOutput(
            success=not bool(result.get("error")),
            summary=reflection[:500],
            artifacts=artifacts,
            metrics={
                "steps_executed": result.get("steps", 0),
                "agent_id": self.agent_id,
            },
        )
