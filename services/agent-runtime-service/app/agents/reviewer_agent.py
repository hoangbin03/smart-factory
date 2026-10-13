"""
Reviewer Agent
Reviews code for quality, security, and best practices.
Tools: Code Analysis Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.nat.agent_runtime import analyze
from app.workspace import Workspace


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
        # Read the ACTUAL code the developer wrote to the workspace.
        workspace = Workspace(task.ws)
        code = self._render_codebase(workspace.read_all())

        # Code review of the real files. When NeMo is enabled for 'reviewer',
        # the ReAct agent can also run its own checks (lint, grep) on the files.
        review = await analyze(
            role="reviewer",
            workflow_id=task.ws,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Perform a comprehensive code review for:
Goal: {task.goal}

Actual code under review:
{code}

Provide:
## Review Summary
## Issues Found (Critical/High/Medium/Low)
## Security Analysis
## Performance Analysis
## Recommendations
## Approval Status (APPROVED/CHANGES_REQUIRED/REJECTED)

Only approve if the code is correct, safe, and meets the goal.""",
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
        upper = review_content.upper()
        approved = "APPROVED" in upper and "CHANGES_REQUIRED" not in upper and "REJECTED" not in upper

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
            metrics={
                "approved": approved,
                # tells the orchestrator to loop back to the developer when not approved
                "needsRework": not approved,
                "reworkFeedback": None if approved else self._extract_issues(review_content),
            },
        )

    def _render_codebase(self, files: dict[str, str]) -> str:
        if not files:
            return "(No source files were found in the workspace — the developer produced no code.)"
        blocks = []
        for name, content in files.items():
            blocks.append(f"--- FILE: {name} ---\n{content[:6000]}")
        return "\n\n".join(blocks)[:24000]

    def _extract_issues(self, review: str) -> str:
        """Pull the 'Issues Found' section back to the developer as rework guidance."""
        lower = review.lower()
        start = lower.find("issues found")
        if start == -1:
            return review[:1500]
        end = lower.find("## ", start + 5)
        section = review[start: end if end != -1 else start + 1500]
        return section.strip()[:1500]
