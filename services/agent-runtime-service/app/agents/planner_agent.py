"""
Planner Agent
Breaks goals into epics, stories, and actionable tasks.
Tools: Planning Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.nat.agent_runtime import analyze


class PlannerAgent(LLMAgent):
    agent_id = "planner_agent"
    role = "planner"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are an experienced Technical Project Manager and Planner.
Your responsibilities:
- Decompose high-level goals into epics, user stories, and technical tasks
- Estimate effort and complexity
- Identify dependencies between tasks
- Create sprint plans
- Assign tasks to the right agent roles

Always structure your output as:
EPIC → Stories → Tasks
Each task must specify: role (architect/developer/reviewer/qa/devops)"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # Generate project plan (via NeMo ReAct when 'planner' enabled)
        project_plan = await analyze(
            role="planner",
            workflow_id=task.ws,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create a detailed project plan for:
Goal: {task.goal}
Context: {task.context}

Structure:
## Epic 1: [Name]
### Story 1.1: [Name]
- Task: [description] | Role: [architect|developer|reviewer|qa|devops] | Points: [1-8]

Create at least 2 epics with 2-3 stories each.""",
        )

        # Generate sprint allocation
        sprint_plan = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""For goal: {task.goal}
Create a sprint plan showing which sprint each story belongs to.
Format:
Sprint 1: [Story names] - Goal: [sprint goal]
Sprint 2: [Story names] - Goal: [sprint goal]""",
        )

        return {
            "output": project_plan,
            "sprint_plan": sprint_plan,
            "steps": len(plan),
        }

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        return AgentTaskOutput(
            success=True,
            summary=f"Project plan created for: {task.goal}",
            artifacts=[
                AgentArtifact(
                    artifact_type="project_plan",
                    name="project_plan.md",
                    content=result.get("output", ""),
                ),
                AgentArtifact(
                    artifact_type="sprint_plan",
                    name="sprint_plan.md",
                    content=result.get("sprint_plan", ""),
                ),
            ],
            metrics={"plan_generated": True},
        )
