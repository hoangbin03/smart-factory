"""
QA Agent
Creates and runs tests, produces defect reports.
Tools: Test Runner Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client


class QAAgent(LLMAgent):
    agent_id = "qa_agent"
    role = "qa"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are a Senior QA Engineer in the Factory Platform.
Your responsibilities:
- Create comprehensive test plans
- Write automated test cases (unit, integration, e2e)
- Identify edge cases and failure scenarios
- Produce defect reports with severity and priority
- Validate acceptance criteria
- Performance testing analysis

Test levels:
1. Unit Tests
2. Integration Tests
3. E2E Tests
4. Performance Tests
5. Security Tests"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # Generate test plan
        test_plan = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create a comprehensive test plan for:
Goal: {task.goal}
Context: {task.context}

Include:
## Test Scope
## Test Cases (Happy path + Edge cases)
## Test Data
## Pass/Fail Criteria""",
        )

        # Generate test report
        test_report = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Analyze and report testing for: {task.goal}
Produce a test execution report with:
- Total tests: X
- Passed: X
- Failed: X
- Blocked: X
- Coverage: X%
- Defects found (severity: critical/high/medium/low)""",
        )

        return {
            "output": test_plan,
            "test_report": test_report,
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
            summary=f"QA testing completed for: {task.goal}",
            artifacts=[
                AgentArtifact(
                    artifact_type="test_plan",
                    name="test_plan.md",
                    content=result.get("output", ""),
                ),
                AgentArtifact(
                    artifact_type="test_report",
                    name="test_report.md",
                    content=result.get("test_report", ""),
                ),
            ],
            metrics={"tests_generated": True},
        )
