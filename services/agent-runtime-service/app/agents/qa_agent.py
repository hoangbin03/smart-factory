"""
QA Agent
Creates and runs tests, produces defect reports.
Tools: Test Runner Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.nat.agent_runtime import analyze
from app.workspace import Workspace


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
        # Independently RUN real verification on the code in the workspace.
        workspace = Workspace(task.ws)
        files = workspace.read_all()
        verification = await workspace.verify()

        # LLM writes a test plan grounded in the real files. When NeMo is enabled
        # for 'qa', the ReAct agent can run additional checks on the workspace.
        file_list = "\n".join(f"- {name} ({len(content)} bytes)" for name, content in files.items()) or "- (no files found)"
        test_plan = await analyze(
            role="qa",
            workflow_id=task.ws,
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create a comprehensive test plan for:
Goal: {task.goal}

Files that were actually delivered:
{file_list}

Include:
## Test Scope
## Test Cases (Happy path + Edge cases)
## Test Data
## Pass/Fail Criteria""",
        )

        return {
            "output": test_plan,
            "verification": verification,
            "files_count": len(files),
            "steps": len(plan),
        }

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        verification = result.get("verification") or {}
        passed = verification.get("passed", 0)
        total = verification.get("total", 0)
        failed = verification.get("failed", 0)
        qa_ok = bool(verification.get("ok", True)) and result.get("files_count", 0) > 0

        return AgentTaskOutput(
            success=True,
            summary=f"QA completed for '{task.goal}': {passed}/{total} checks passed"
            + ("" if qa_ok else f" — {failed} FAILED"),
            artifacts=[
                AgentArtifact(
                    artifact_type="test_plan",
                    name="test_plan.md",
                    content=result.get("output", ""),
                ),
                AgentArtifact(
                    artifact_type="test_report",
                    name="test_report.md",
                    content=self._render_report(task, verification, result.get("files_count", 0)),
                ),
            ],
            metrics={
                "checks_total": total,
                "checks_passed": passed,
                "checks_failed": failed,
                "qa_passed": qa_ok,
                "needsRework": not qa_ok,
                "reworkFeedback": None if qa_ok else self._qa_feedback(verification, result.get("files_count", 0)),
            },
        )

    def _render_report(self, task: AgentTaskInput, verification: dict, files_count: int) -> str:
        checks = verification.get("checks", [])
        lines = [
            f"# QA Test Report — {task.goal}",
            "",
            f"- Files delivered: {files_count}",
            f"- Automated checks: {verification.get('passed', 0)}/{verification.get('total', 0)} passed",
            f"- Verdict: **{'PASS' if verification.get('ok', True) and files_count else 'FAIL'}**",
            "",
            "## Executed Checks",
            "",
        ]
        if not checks:
            lines.append("_No automated checks were applicable._")
        for c in checks:
            status = "✅ PASS" if c.get("ok") else "❌ FAIL"
            lines.append(f"- {status} — `{c.get('file')}` [{c.get('check')}]")
            if not c.get("ok") and c.get("detail"):
                lines.append(f"    ↳ {c.get('detail')[:300]}")
        return "\n".join(lines)

    def _qa_feedback(self, verification: dict, files_count: int) -> str:
        if files_count == 0:
            return "No files were delivered to the workspace. The developer must produce actual code files."
        failed = [c for c in verification.get("checks", []) if not c.get("ok")]
        return "QA found failing checks that must be fixed:\n" + "\n".join(
            f"- {c.get('file')} ({c.get('check')}): {c.get('detail', '')[:200]}" for c in failed
        )
