"""
Reviewer Agent
Reviews code for quality, security, and best practices.
Tools: Code Analysis Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client


class ReviewerAgent(LLMAgent):
    agent_id = "reviewer_agent"
    role = "reviewer"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are a Senior Code Reviewer in the Factory Platform.
Your responsibilities:
- Review code for correctness, performance, and security
- Check adherence to SOLID and clean code principles
- Identify security vulnerabilities (OWASP Top 10)
- Suggest improvements and refactoring opportunities
- Approve or reject code with clear reasoning

Review dimensions:
1. Correctness
2. Security (SAST)
3. Performance
4. Maintainability
5. Test Coverage
6. Documentation"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # Code review
        review = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Perform a comprehensive code review for:
Goal: {task.goal}
Context: {task.context}

Provide:
## Review Summary
## Issues Found (Critical/High/Medium/Low)
## Security Analysis
## Performance Analysis
## Recommendations
## Approval Status (APPROVED/CHANGES_REQUIRED/REJECTED)""",
        )

        # Security scan
        security = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Security analysis for: {task.goal}
Check for:
- SQL injection
- XSS vulnerabilities
- Authentication issues
- Authorization bypass
- Data exposure
- Dependency vulnerabilities""",
        )

        return {
            "output": review,
            "security_report": security,
            "steps": len(plan),
        }

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        review_content = result.get("output", "")
        approved = "APPROVED" in review_content.upper() and "CHANGES_REQUIRED" not in review_content.upper()

        return AgentTaskOutput(
            success=True,
            summary=f"Code review completed. Status: {'APPROVED' if approved else 'CHANGES_REQUIRED'}",
            artifacts=[
                AgentArtifact(
                    artifact_type="review_report",
                    name="review_report.md",
                    content=review_content,
                ),
                AgentArtifact(
                    artifact_type="security_report",
                    name="security_report.md",
                    content=result.get("security_report", ""),
                ),
            ],
            metrics={"approved": approved},
        )
