"""
Developer Agent
Writes, refactors, and tests source code.
Tools: Git Tool, Filesystem Tool, Terminal Tool, Search Tool
"""
import json
import re
import unicodedata
from typing import Any

from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.workspace import Workspace


class DeveloperAgent(LLMAgent):
    agent_id = "developer_agent"
    role = "developer"
    version = "1.0.0"

    SYSTEM_PROMPT = """You are a Senior Software Engineer in the Factory Platform.
Your responsibilities:
- Turn product requirements into runnable, reviewable artifacts
- Prefer complete files over prose-only answers
- Follow clean code, accessible UI, and safe client-side logic
- Handle errors and edge cases
- Return structured artifacts that downstream preview and delivery tools can consume"""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        context = task.context if isinstance(task.context, dict) else {}
        upstream = context.get("upstream", {}) if isinstance(context.get("upstream"), dict) else {}
        rework = context.get("reworkFeedback")

        product = None
        templates = context.get("templates") if isinstance(context, dict) else None

        # A non-empty workspace means we're working on an EXISTING codebase — a
        # project's shared code, an imported repo, or a prior build/rework round.
        # In that case the developer must READ and MODIFY the real files, not
        # regenerate the project from scratch (which would destroy existing code).
        existing_project = not Workspace(task.ws).ensure().is_empty()

        # Preferred path: run the developer through the NVIDIA NeMo Agent Toolkit
        # (NAT) ReAct agent, which reasons and calls the real tool functions itself.
        from app.core.config import settings
        if settings.USE_NAT_DEVELOPER:
            try:
                from app.nat.developer_runtime import run_nat_developer
                product = await run_nat_developer(
                    task.ws, task.goal, upstream, rework, context.get("skills"), templates,
                    context.get("memory"), existing_project,
                )
            except Exception as exc:  # noqa: BLE001 — degrade gracefully to direct generation
                self.logger.warning("NAT developer failed, falling back to direct generation", error=str(exc))
                product = None

        # Fallback path: template/skill-driven generation. The product shape
        # (tech stack, files) is decided by the assigned template + the goal —
        # NOT hardcoded to a fixed 3-file static web page.
        if product is None:
            # wipe any partial files a failed NAT run left behind — but NOT when we
            # imported an existing repo (regenerating would destroy the real code).
            if not existing_project:
                try:
                    Workspace(task.ws).ensure().clear()
                except Exception as exc:  # noqa: BLE001
                    self.logger.warning("Workspace clear before fallback failed", error=str(exc))

            product = await self._build_from_blueprint(task, plan, upstream, rework, templates)

        # Turn the generated files into a REAL project on disk, verify it, commit it.
        return await self._materialize(task, product, plan)

    async def _build_from_blueprint(
        self,
        task: AgentTaskInput,
        plan: list[str],
        upstream: dict[str, Any] | None,
        rework: Any,
        templates: list | None,
    ) -> dict[str, Any]:
        """
        Flexible, template-driven product generation. Produces however many files
        the project needs in whatever stack the goal/template implies.
        """
        blueprint = self._format_templates(templates)
        follow = (
            "Follow the PROJECT TEMPLATE above EXACTLY — its stack, file structure and conventions."
            if templates else
            "Choose the appropriate stack and file structure for the goal. "
            "If it is a web / UI / game goal, produce a runnable static frontend whose index.html "
            "references only local assets."
        )
        response = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Build a COMPLETE, runnable project for this request.

Goal: {task.goal}
{self._format_upstream(upstream)}
{self._rework_note(rework)}
{blueprint}Implementation plan:
{self._format_plan(plan)}

{follow}

Return ONLY valid JSON (no markdown fences) with this shape:
{{
  "product_type": "short label, e.g. static_frontend | react_app | node_api | python_service | cli_tool",
  "summary": "short product summary",
  "files": [
    {{"name": "relative/path.ext", "artifact_type": "html|css|javascript|source_code|documentation|config", "content": "COMPLETE file content"}}
  ],
  "acceptance_criteria": ["criterion 1", "criterion 2"]
}}

Hard requirements:
- Produce AS MANY files as the project genuinely needs — do not force a fixed number.
- Every file must contain complete, runnable content. No placeholders, no TODOs.
- Use correct relative paths (e.g. src/App.jsx, styles/main.css) matching the chosen stack.
""",
            temperature=0.2,
            max_tokens=8192,
        )

        parsed = self._parse_artifact_contract(response)
        if parsed:
            parsed["steps"] = len(plan)
            parsed["generated_by"] = "template_blueprint" if templates else "llm_artifact_contract"
            return parsed

        # last resort: a minimal runnable scaffold so the workflow still delivers something
        fallback = self._build_generic_frontend_fallback(task, plan)
        fallback["llm_response"] = response[:4000]
        return fallback

    def _format_templates(self, templates: list | None) -> str:
        if not templates:
            return ""
        blocks = [f"— {t.get('name')}:\n{t.get('instructions')}" for t in templates if isinstance(t, dict)]
        if not blocks:
            return ""
        return "PROJECT TEMPLATE (build the product to match this):\n" + "\n\n".join(blocks) + "\n\n"

    async def _materialize(self, task: AgentTaskInput, product: dict[str, Any], plan: list[str]) -> dict[str, Any]:
        """Write files to an isolated workspace, run real checks, and git-commit."""
        files = product.get("files") or []
        workspace = Workspace(task.ws).ensure()
        try:
            written = workspace.write_files(files)
            verification = await workspace.verify()
            commit = await workspace.commit(f"developer_agent: {task.goal[:80]}")
            disk_files = workspace.snapshot_as_files() or files
        except Exception as exc:  # noqa: BLE001 — never let tool failure crash the agent
            self.logger.error("Workspace materialization failed", error=str(exc))
            written, verification, commit, disk_files = [], {"ok": False, "error": str(exc), "checks": []}, {}, files

        product["files"] = disk_files
        product["written_files"] = written
        product["verification"] = verification
        product["git"] = commit
        product["workspace_path"] = str(workspace.path)
        product["steps"] = len(plan)
        product["output"] = disk_files[0]["content"] if disk_files else product.get("output", "")
        return product

    def _parse_artifact_contract(self, response: str) -> dict[str, Any] | None:
        payload = self._extract_json_object(response)
        if not payload:
            return None

        files = payload.get("files")
        if not isinstance(files, list):
            return None

        normalized_files = []
        for item in files:
            if not isinstance(item, dict):
                continue
            name = self._sanitize_artifact_name(str(item.get("name") or "artifact.txt"))
            content = item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue
            normalized_files.append({
                "name": name,
                "artifact_type": str(item.get("artifact_type") or self._infer_artifact_type(name)),
                "content": content,
            })

        if not normalized_files:
            return None

        return {
            "files": normalized_files,
            "output": normalized_files[0]["content"],
            "summary": str(payload.get("summary") or "Product artifacts generated."),
            "product_type": str(payload.get("product_type") or "artifact_package"),
            "acceptance_criteria": payload.get("acceptance_criteria") if isinstance(payload.get("acceptance_criteria"), list) else [],
        }

    def _extract_json_object(self, response: str) -> dict[str, Any] | None:
        text = response.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        candidates = [text]
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if match:
            candidates.append(match.group(0))

        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue
        return None

    def _sanitize_artifact_name(self, name: str) -> str:
        """Normalize an LLM-provided filename into a safe relative path (no traversal)."""
        cleaned = (name or "").strip().replace("\\", "/")
        # drop leading slashes and any parent-directory hops
        parts = [p for p in cleaned.split("/") if p not in ("", ".", "..")]
        safe_parts = []
        for part in parts:
            safe = re.sub(r"[^A-Za-z0-9._-]", "_", part)
            if safe:
                safe_parts.append(safe)
        result = "/".join(safe_parts)
        return result or "artifact.txt"

    def _infer_artifact_type(self, name: str) -> str:
        lower = name.lower()
        if lower.endswith(".html"):
            return "html"
        if lower.endswith(".css"):
            return "css"
        if lower.endswith(".js"):
            return "javascript"
        if lower.endswith(".md"):
            return "documentation"
        return "file"

    def _build_generic_frontend_fallback(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        title = self._title_from_goal(task.goal)
        safe_goal = self._escape_html(task.goal)
        plan_items = "".join(f"<li>{self._escape_html(step)}</li>" for step in plan[:6]) or "<li>Define the product behavior</li>"
        html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">Smart Factory Preview</p>
      <h1>{title}</h1>
      <p class="goal">{safe_goal}</p>
      <div class="actions">
        <button type="button" id="primaryAction">Run demo</button>
        <button type="button" id="resetAction">Reset</button>
      </div>
    </section>
    <section class="workspace" aria-live="polite">
      <div class="status" id="status">Ready</div>
      <label>
        Input
        <input id="demoInput" placeholder="Type something to test the generated product" />
      </label>
      <div class="output" id="output">The generated product will respond here.</div>
      <h2>Build plan</h2>
      <ol>{plan_items}</ol>
    </section>
  </main>
</body>
</html>"""
        css = """:root {
  color-scheme: light;
  --bg: #f8fafc;
  --panel: #ffffff;
  --text: #0f172a;
  --muted: #64748b;
  --accent: #2563eb;
  --line: #dbe3ef;
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: var(--bg); color: var(--text); }
.shell { width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 32px 0; display: grid; grid-template-columns: 0.9fr 1.1fr; gap: 24px; align-items: start; }
.hero, .workspace { background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 24px; box-shadow: 0 18px 45px rgba(15, 23, 42, 0.08); }
.eyebrow { margin: 0 0 10px; color: var(--accent); font-weight: 800; font-size: 12px; text-transform: uppercase; }
h1 { margin: 0; font-size: 34px; line-height: 1.05; letter-spacing: 0; }
.goal { color: var(--muted); line-height: 1.6; }
.actions { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 20px; }
button { border: 0; border-radius: 8px; padding: 11px 14px; font-weight: 800; cursor: pointer; }
#primaryAction { background: var(--accent); color: white; }
#resetAction { background: #e2e8f0; color: var(--text); }
.status { display: inline-flex; padding: 6px 10px; border-radius: 999px; background: #dcfce7; color: #166534; font-weight: 800; font-size: 13px; }
label { display: grid; gap: 8px; margin-top: 18px; color: var(--muted); font-weight: 700; }
input { width: 100%; border: 1px solid var(--line); border-radius: 8px; padding: 12px; font: inherit; color: var(--text); }
.output { margin-top: 16px; min-height: 110px; border: 1px dashed var(--line); border-radius: 8px; padding: 16px; background: #f8fafc; line-height: 1.55; }
h2 { margin: 24px 0 10px; font-size: 16px; }
li { margin: 8px 0; color: var(--muted); }
@media (max-width: 820px) { .shell { grid-template-columns: 1fr; } h1 { font-size: 28px; } }
"""
        js = """const input = document.querySelector('#demoInput');
const output = document.querySelector('#output');
const status = document.querySelector('#status');
const primary = document.querySelector('#primaryAction');
const reset = document.querySelector('#resetAction');

function render(message, state = 'Ready') {
  output.textContent = message;
  status.textContent = state;
}

primary.addEventListener('click', () => {
  const value = input.value.trim();
  render(value ? `Demo processed: ${value}` : 'Demo is running. Add input to make it more specific.', 'Running');
});

reset.addEventListener('click', () => {
  input.value = '';
  render('The generated product will respond here.', 'Ready');
});

input.addEventListener('input', () => {
  render(input.value ? `Live input: ${input.value}` : 'The generated product will respond here.', 'Editing');
});
"""
        return {
            "files": [
                {"name": "index.html", "artifact_type": "html", "content": html},
                {"name": "styles.css", "artifact_type": "css", "content": css},
                {"name": "script.js", "artifact_type": "javascript", "content": js},
            ],
            "output": html,
            "steps": len(plan),
            "product_type": "static_frontend_fallback",
            "summary": "Fallback runnable preview generated because the LLM did not return a valid artifact contract.",
        }

    def _format_plan(self, plan: list[str]) -> str:
        return "\n".join(f"{index + 1}. {step}" for index, step in enumerate(plan)) or "1. Build the requested product"

    def _format_upstream(self, upstream: dict[str, Any] | None) -> str:
        """Feed the architect's design and planner's breakdown into the build prompt."""
        if not upstream:
            return ""
        parts: list[str] = []
        arch = upstream.get("architect_agent")
        planner = upstream.get("planner_agent")
        if arch:
            parts.append(f"Architecture & design decisions to follow:\n{str(arch)[:2500]}")
        if planner:
            parts.append(f"Implementation breakdown from the planner:\n{str(planner)[:1500]}")
        return ("\n\n".join(parts) + "\n") if parts else ""

    def _rework_note(self, rework: Any) -> str:
        """When a reviewer/QA sent the work back, tell the developer exactly what to fix."""
        if not rework:
            return ""
        return (
            "\nIMPORTANT — this is a REWORK. A previous version failed review/QA. "
            "Fix ALL of the following issues in this iteration:\n"
            f"{str(rework)[:2000]}\n"
        )

    def _render_build_report(self, task, result, verification, git_info) -> str:
        checks = verification.get("checks", [])
        lines = [
            f"# Build Report — {task.goal}",
            "",
            f"- Product type: `{result.get('product_type', 'artifact_package')}`",
            f"- Files written: {len(result.get('written_files', result.get('files', [])))}",
            f"- Verification: **{'PASSED' if verification.get('ok', True) else 'FAILED'}** "
            f"({verification.get('passed', 0)}/{verification.get('total', 0)} checks passed)",
            f"- Node runtime available: {verification.get('node_available', False)}",
        ]
        if git_info.get("committed"):
            lines.append(f"- Git commit: `{git_info.get('hash', '')}` — {git_info.get('message', '')}")
        else:
            lines.append("- Git commit: not created")
        lines += ["", "## Checks", ""]
        if not checks:
            lines.append("_No automated checks ran for these file types._")
        for c in checks:
            status = "✅" if c.get("ok") else "❌"
            lines.append(f"- {status} `{c.get('file')}` — {c.get('check')}")
            if not c.get("ok") and c.get("detail"):
                lines.append(f"  ```\n  {c.get('detail')[:400]}\n  ```")
        return "\n".join(lines)

    def _build_summary(self, task, result, verification, git_info) -> str:
        base = str(result.get("summary") or f"Product built for: {task.goal}")
        status = "verified ✅" if verification.get("ok", True) else f"verification FAILED ({verification.get('failed', 0)} issue(s))"
        commit = f", commit {git_info.get('hash')}" if git_info.get("hash") else ""
        return f"{base} — {status}{commit}"

    def _verification_feedback(self, verification) -> str:
        failed = [c for c in verification.get("checks", []) if not c.get("ok")]
        if not failed:
            return "Verification failed. Ensure all files are syntactically valid and runnable."
        return "Fix these verification failures:\n" + "\n".join(
            f"- {c.get('file')} ({c.get('check')}): {c.get('detail', '')[:200]}" for c in failed
        )

    def _normalize(self, value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.lower())
        return "".join(char for char in normalized if not unicodedata.combining(char))

    def _title_from_goal(self, goal: str) -> str:
        words = re.findall(r"[A-Za-z0-9]+", self._normalize(goal))[:6]
        return " ".join(word.capitalize() for word in words) or "Smart Factory Product"

    def _escape_html(self, value: str) -> str:
        return (
            value.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        if isinstance(result.get("files"), list):
            artifacts = [
                AgentArtifact(
                    artifact_type=str(file.get("artifact_type", "file")),
                    name=self._sanitize_artifact_name(str(file.get("name", "artifact.txt"))),
                    content=str(file.get("content", "")),
                    metadata={
                        "workflow_id": task.workflow_id,
                        "path": self._sanitize_artifact_name(str(file.get("name", "artifact.txt"))),
                        "product_type": result.get("product_type", "artifact_package"),
                        "generated_by": result.get("generated_by", "developer_agent"),
                    },
                )
                for file in result["files"]
            ]

            verification = result.get("verification") or {}
            git_info = result.get("git") or {}
            build_ok = bool(verification.get("ok", True))
            artifacts.append(
                AgentArtifact(
                    artifact_type="build_report",
                    name="build_report.md",
                    content=self._render_build_report(task, result, verification, git_info),
                    metadata={"workflow_id": task.workflow_id, "verification_ok": build_ok},
                )
            )

            has_preview = any(artifact.name.lower() == "index.html" for artifact in artifacts)
            return AgentTaskOutput(
                success=build_ok,
                summary=self._build_summary(task, result, verification, git_info),
                artifacts=artifacts,
                metrics={
                    "files_created": len(result["files"]),
                    "steps_executed": result.get("steps", 0),
                    "has_preview": has_preview,
                    "product_type": result.get("product_type", "artifact_package"),
                    "checks_total": verification.get("total", 0),
                    "checks_passed": verification.get("passed", 0),
                    "checks_failed": verification.get("failed", 0),
                    "verification_ok": build_ok,
                    "commit": git_info.get("hash", ""),
                    # signals the orchestrator to send this back to the developer if a downstream gate fails
                    "reworkFeedback": self._verification_feedback(verification) if not build_ok else None,
                },
                next_action="Open workflow preview" if has_preview else "Review generated artifacts",
            )

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
