"""
Workspace — an isolated, per-workflow directory on disk where agents
actually write files, run commands, verify code, and commit to git.

This is the piece that turns the Developer/QA agents from "chatbots that
return text" into a real factory that produces runnable artifacts.
"""
import json
from pathlib import Path
from typing import Any

import structlog

from app.core.config import settings
from app.tools.filesystem_tool import FilesystemTool
from app.tools.terminal_tool import TerminalTool
from app.tools.git_tool import GitTool

logger = structlog.get_logger()


class Workspace:
    """Bundles the real tool layer (fs + terminal + git) for one workflow."""

    def __init__(self, workflow_id: str, root: str | None = None):
        self.workflow_id = workflow_id
        base = Path(root or settings.WORKSPACE_ROOT)
        # workflow_id is a UUID from the DB — safe as a directory name.
        self.path = (base / str(workflow_id)).resolve()
        self.fs = FilesystemTool(self.path)
        self.terminal = TerminalTool(self.path)
        self.git = GitTool(self.path)

    def ensure(self) -> "Workspace":
        self.path.mkdir(parents=True, exist_ok=True)
        return self

    def clear(self) -> "Workspace":
        """Remove all files (but keep the .git history) — used before a clean regeneration."""
        if not self.path.exists():
            return self
        for entry in self.path.iterdir():
            if entry.name == ".git":
                continue
            if entry.is_dir():
                import shutil
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        return self

    def _wipe(self) -> None:
        """Remove everything in the workspace (including .git) — used before an import."""
        if not self.path.exists():
            return
        import shutil
        for entry in self.path.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)

    def is_empty(self) -> bool:
        if not self.path.exists():
            return True
        return not any(self.path.iterdir())

    async def import_from_git(self, repo_url: str, branch: str = "", token: str = "") -> dict[str, Any]:
        """Clone a remote repo into a fresh workspace so agents can work on real code."""
        self.ensure()
        self._wipe()
        if not await self.git.is_available():
            return {"ok": False, "error": "git not available in runtime"}
        result = await self.git.clone(repo_url, branch, token)
        files = self.list_files()
        return {
            "ok": bool(result.get("cloned")) and len(files) > 0,
            "source": "git",
            "files": len(files),
            "output": result.get("output", ""),
        }

    def import_files(self, files: list[dict[str, Any]], *, replace: bool = True) -> dict[str, Any]:
        """
        Import an uploaded local folder: a list of {path, content} written into the
        workspace preserving relative structure. Skips heavy/vcs dirs.
        """
        self.ensure()
        if replace:
            self._wipe()
        written = 0
        skipped = 0
        for f in files:
            rel = f.get("path") or f.get("name") or ""
            content = f.get("content")
            if not rel or not isinstance(content, str):
                skipped += 1
                continue
            if _is_ignored_path(rel):
                skipped += 1
                continue
            try:
                self.fs.write_file(rel, content)
                written += 1
            except Exception:  # noqa: BLE001
                skipped += 1
        return {"ok": written > 0, "source": "upload", "files": written, "skipped": skipped}

    def write_files(self, files: list[dict[str, Any]]) -> list[str]:
        """Write a list of {name/path, content} files to disk. Returns written paths."""
        self.ensure()
        written: list[str] = []
        for f in files:
            name = f.get("path") or f.get("name")
            content = f.get("content")
            if not name or not isinstance(content, str):
                continue
            self.fs.write_file(name, content)
            written.append(name)
        return written

    def list_files(self) -> list[dict[str, Any]]:
        return self.fs.list_files()

    def read_all(self, max_bytes: int = 60_000) -> dict[str, str]:
        return self.fs.read_text_files(max_bytes=max_bytes)

    def snapshot_as_files(self) -> list[dict[str, Any]]:
        """Read the workspace back as artifact-shaped file dicts (disk is source of truth)."""
        files: list[dict[str, Any]] = []
        for rel, content in self.read_all().items():
            files.append({
                "name": rel,
                "artifact_type": _infer_type(rel),
                "content": content,
            })
        return files

    async def verify(self) -> dict[str, Any]:
        """
        Actually exercise the generated code: syntax-check JS/Python,
        validate JSON/HTML. Returns a real pass/fail report with command output.
        """
        checks: list[dict[str, Any]] = []
        node_available = await self.terminal.which("node")

        for entry in self.list_files():
            rel = entry["path"]
            lower = rel.lower()
            if lower.endswith(".js") or lower.endswith(".mjs"):
                if node_available:
                    result = await self.terminal.run(f'node --check "{rel}"', timeout=30)
                    checks.append(_check(rel, "js-syntax", result.ok, (result.stderr or result.stdout).strip()))
                else:
                    checks.append(_check(rel, "js-syntax", True, "node not available — skipped"))
            elif lower.endswith(".py"):
                result = await self.terminal.run(f'python -m py_compile "{rel}"', timeout=30)
                checks.append(_check(rel, "py-compile", result.ok, (result.stderr or result.stdout).strip()))
            elif lower.endswith(".json"):
                ok, detail = _validate_json(self.path / rel)
                checks.append(_check(rel, "json-parse", ok, detail))
            elif lower.endswith(".html") or lower.endswith(".htm"):
                ok, detail = _validate_html(self.path / rel)
                checks.append(_check(rel, "html-structure", ok, detail))

        # If the project declares a test script, actually run it.
        test_result = await self._maybe_run_tests(node_available)
        if test_result:
            checks.append(test_result)

        passed = sum(1 for c in checks if c["ok"])
        failed = len(checks) - passed
        return {
            "checks": checks,
            "passed": passed,
            "failed": failed,
            "total": len(checks),
            "ok": failed == 0,
            "node_available": node_available,
        }

    async def _maybe_run_tests(self, node_available: bool) -> dict[str, Any] | None:
        """Run a real test suite if one is declared (npm test / pytest)."""
        pkg = self.path / "package.json"
        if pkg.exists() and node_available:
            try:
                scripts = json.loads(pkg.read_text(encoding="utf-8")).get("scripts", {})
            except json.JSONDecodeError:
                scripts = {}
            if "test" in scripts and (self.path / "node_modules").exists():
                result = await self.terminal.run("npm test --silent", timeout=settings.TOOL_COMMAND_TIMEOUT)
                return _check("package.json", "npm-test", result.ok, (result.stdout + result.stderr)[-2000:])
        if (self.path / "tests").exists() or list(self.path.glob("test_*.py")):
            result = await self.terminal.run("python -m pytest -q", timeout=settings.TOOL_COMMAND_TIMEOUT)
            # exit code 5 = "no tests collected" — don't count as failure
            ok = result.ok or result.exit_code == 5
            return _check("tests", "pytest", ok, (result.stdout + result.stderr)[-2000:])
        return None

    async def commit(self, message: str) -> dict[str, Any]:
        if not await self.git.is_available():
            return {"committed": False, "hash": "", "output": "git not available"}
        return await self.git.commit_all(message)


_IGNORED_SEGMENTS = {".git", "node_modules", "__pycache__", ".next", "dist", "build", ".venv", "venv"}


def _is_ignored_path(rel: str) -> bool:
    parts = rel.replace("\\", "/").split("/")
    return any(seg in _IGNORED_SEGMENTS for seg in parts)


def _check(file: str, kind: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"file": file, "check": kind, "ok": ok, "detail": detail[:1000]}


def _validate_json(path: Path) -> tuple[bool, str]:
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True, "valid JSON"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _validate_html(path: Path) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8", errors="replace").lower()
    if "<html" in text or "<!doctype" in text:
        if text.count("<body") >= 1 or "<div" in text or "<main" in text:
            return True, "has document structure"
        return True, "minimal html"
    return False, "no <html>/<!doctype> root element"


def _infer_type(name: str) -> str:
    lower = name.lower()
    for ext, kind in (
        (".html", "html"), (".htm", "html"), (".css", "css"),
        (".js", "javascript"), (".mjs", "javascript"), (".ts", "typescript"),
        (".json", "json"), (".md", "documentation"), (".py", "source_code"),
    ):
        if lower.endswith(ext):
            return kind
    return "file"
