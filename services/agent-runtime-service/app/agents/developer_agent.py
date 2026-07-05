"""
Developer Agent
Writes, refactors, and tests source code.
Tools: Git Tool, Filesystem Tool, Terminal Tool, Search Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client


class DeveloperAgent(LLMAgent):
    agent_id = "developer_agent"
    role = "developer"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are a Senior Software Engineer in the Factory Platform.
Your responsibilities:
- Write production-quality code in any language
- Follow clean code, SOLID, and DRY principles
- Write comprehensive unit tests
- Handle errors and edge cases
- Add proper documentation and comments
- Create meaningful commit messages

Always output:
1. Source code files
2. Test files
3. Pull request description"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # Generate source code
        source_code = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Implement the following:
Goal: {task.goal}
Context: {task.context}
Implementation plan:
{chr(10).join(f'{i+1}. {step}' for i, step in enumerate(plan))}

Write complete, production-ready code. Include:
- Main implementation
- Error handling
- Type annotations
- JSDoc/docstrings""",
        )

        # Generate tests
        tests = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Write comprehensive tests for:
Goal: {task.goal}

Include:
- Unit tests for all functions
- Edge cases
- Error scenarios
- Integration test examples""",
        )

        # Generate PR summary
        pr_summary = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Write a Pull Request description for:
Goal: {task.goal}

Format:
## Summary
## Changes
## Testing
## Notes""",
        )

        return {
            "output": source_code,
            "tests": tests,
            "pr_summary": pr_summary,
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
            summary=f"Code implemented for: {task.goal}",
            artifacts=[
                AgentArtifact(
                    artifact_type="source_code",
                    name="implementation.md",
                    content=result.get("output", ""),
                ),
                AgentArtifact(
                    artifact_type="test_code",
                    name="tests.md",
                    content=result.get("tests", ""),
                ),
                AgentArtifact(
                    artifact_type="pull_request",
                    name="pull_request.md",
                    content=result.get("pr_summary", ""),
                ),
            ],
            metrics={"files_created": 3},
        )
