"""
Architect Agent
Designs system architecture, services, and database schemas.
Tools: Search Tool, Documentation Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.nat.agent_runtime import analyze


class ArchitectAgent(LLMAgent):
    agent_id = "architect_agent"
    role = "architect"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are a Senior Software Architect in the Factory Platform.
Your responsibilities:
- Design scalable microservice architectures
- Create database schemas and ERD
- Define API contracts and interfaces
- Document technical decisions (ADRs)
- Follow SOLID principles and clean architecture

Output format: Always produce structured documents in Markdown.
Never write actual code — focus on architecture and design."""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # Generate architecture document (via NeMo ReAct when 'architect' enabled)
        arch_doc = await analyze(
            role="architect",
            workflow_id=task.ws,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Design the architecture for:
Goal: {task.goal}
Context: {task.context}
Plan steps: {plan}

Produce:
1. Architecture Overview
2. Service Design
3. Database Schema
4. API Contract
5. Key Decisions (ADRs)""",
        )

        # Generate service design
        service_design = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Based on the goal: {task.goal}
List all microservices needed with:
- Service name
- Responsibilities
- API endpoints
- Database tables
- Dependencies""",
        )

        return {
            "output": arch_doc,
            "service_design": service_design,
            "steps": len(plan),
        }

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        artifacts = [
            AgentArtifact(
                artifact_type="architecture_document",
                name="architecture_design.md",
                content=result.get("output", ""),
                metadata={"workflow_id": task.workflow_id},
            ),
            AgentArtifact(
                artifact_type="service_design",
                name="service_design.md",
                content=result.get("service_design", ""),
                metadata={"workflow_id": task.workflow_id},
            ),
        ]

        return AgentTaskOutput(
            success=True,
            summary=f"Architecture designed for: {task.goal}",
            artifacts=artifacts,
            metrics={"documents_produced": len(artifacts)},
        )
