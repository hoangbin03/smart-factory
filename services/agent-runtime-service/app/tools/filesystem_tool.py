"""
Filesystem Tool
Gives agents real, sandboxed read/write access to a workspace directory.
Every path is resolved and confined to the workspace root — no path traversal.
"""
from pathlib import Path
from typing import Any

from app.tools.base_tool import BaseTool, ToolInput, ToolOutput


class FilesystemTool(BaseTool):
    tool_id = "filesystem_tool"
    description = "Sandboxed filesystem access (read/write/list/delete) confined to a workspace."
    version = "1.0.0"

    def __init__(self, workspace_root: str | Path):
        super().__init__()
        self.root = Path(workspace_root).resolve()

    def _safe_path(self, relative: str) -> Path:
        """Resolve a path and guarantee it stays inside the workspace root."""
        candidate = (self.root / relative).resolve()
        if candidate != self.root and self.root not in candidate.parents:
            raise ValueError(f"Path escapes workspace sandbox: {relative}")
        return candidate

    def write_file(self, relative: str, content: str) -> Path:
        path = self._safe_path(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def read_file(self, relative: str) -> str:
        return self._safe_path(relative).read_text(encoding="utf-8")

    def exists(self, relative: str) -> bool:
        return self._safe_path(relative).exists()

    def list_files(self, skip_dirs: tuple[str, ...] = (".git", "node_modules", "__pycache__")) -> list[dict[str, Any]]:
        """List all files in the workspace as {path, size} (relative paths)."""
        results: list[dict[str, Any]] = []
        if not self.root.exists():
            return results
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(self.root)
            if any(part in skip_dirs for part in rel.parts):
                continue
            results.append({"path": str(rel).replace("\\", "/"), "size": path.stat().st_size})
        return results

    def read_text_files(self, max_bytes: int = 60_000) -> dict[str, str]:
        """Read all text files back as {relative_path: content}, capped per file."""
        out: dict[str, str] = {}
        for entry in self.list_files():
            rel = entry["path"]
            try:
                content = self._safe_path(rel).read_text(encoding="utf-8")
            except (UnicodeDecodeError, ValueError):
                continue  # skip binary/unsafe
            out[rel] = content[:max_bytes]
        return out

    async def _execute(self, input: ToolInput) -> ToolOutput:
        action = input.action
        params = input.parameters
        try:
            if action == "write_file":
                path = self.write_file(params["path"], params.get("content", ""))
                return ToolOutput(success=True, data={"path": str(path.relative_to(self.root))})
            if action == "read_file":
                return ToolOutput(success=True, data=self.read_file(params["path"]))
            if action == "list_files":
                return ToolOutput(success=True, data=self.list_files())
            if action == "exists":
                return ToolOutput(success=True, data=self.exists(params["path"]))
            return ToolOutput(success=False, error=f"Unknown action: {action}")
        except Exception as exc:  # noqa: BLE001 — surfaced to the agent as a tool error
            return ToolOutput(success=False, error=str(exc))
