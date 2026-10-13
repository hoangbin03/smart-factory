"""
Git Tool
Real version control inside the workspace: init, stage, commit, log, diff.
Built on top of TerminalTool so every git action is a real subprocess.
"""
from pathlib import Path

from app.tools.base_tool import BaseTool, ToolInput, ToolOutput
from app.tools.terminal_tool import TerminalTool

# Deterministic identity so commits work in a fresh, headless container.
GIT_ENV = (
    'GIT_AUTHOR_NAME="Factory Developer" GIT_AUTHOR_EMAIL="dev@smart-factory.local" '
    'GIT_COMMITTER_NAME="Factory Developer" GIT_COMMITTER_EMAIL="dev@smart-factory.local"'
)


class GitTool(BaseTool):
    tool_id = "git_tool"
    description = "Version control (init/add/commit/log/diff) for the workspace."
    version = "1.0.0"

    def __init__(self, workspace_root: str | Path):
        super().__init__()
        self.root = Path(workspace_root).resolve()
        self.terminal = TerminalTool(self.root)

    async def is_available(self) -> bool:
        return await self.terminal.which("git")

    async def is_repo(self) -> bool:
        return (self.root / ".git").exists()

    async def init(self) -> bool:
        if await self.is_repo():
            return True
        result = await self.terminal.run("git init -q && git checkout -q -b main 2>/dev/null || git init -q")
        return result.ok

    async def commit_all(self, message: str) -> dict:
        """Stage everything and commit. Returns {committed, hash, output}."""
        await self.init()
        safe_message = message.replace('"', "'").replace("\n", " ")[:200]
        result = await self.terminal.run(
            f'git add -A && {GIT_ENV} git commit -q -m "{safe_message}"'
        )
        commit_hash = ""
        if result.ok:
            head = await self.terminal.run("git rev-parse --short HEAD")
            commit_hash = head.stdout.strip() if head.ok else ""
        return {
            "committed": result.ok,
            "hash": commit_hash,
            "message": safe_message,
            "output": (result.stdout + result.stderr).strip(),
        }

    async def push_to_remote(self, remote_url: str, token: str = "", branch: str = "main") -> dict:
        """
        Push the workspace repo to a remote (e.g. GitHub). If a token is provided it
        is injected into the HTTPS URL for auth. Returns {pushed, output}.
        """
        await self.init()
        # ensure there is at least one commit
        await self.commit_all("factory: publish")
        url = remote_url
        if token and remote_url.startswith("https://"):
            url = remote_url.replace("https://", f"https://x-access-token:{token}@", 1)
        # set/replace origin, then push
        cmd = (
            f'git remote remove origin 2>/dev/null; '
            f'git remote add origin "{url}" && '
            f'git branch -M {branch} && '
            f'git push -u origin {branch} --force'
        )
        result = await self.terminal.run(cmd, timeout=90)
        return {"pushed": result.ok, "output": (result.stdout + result.stderr)[-2000:]}

    async def clone(self, repo_url: str, branch: str = "", token: str = "") -> dict:
        """
        Clone a remote repo into the (already-empty) workspace root. If a token is
        provided it is injected into the HTTPS URL for private repos.
        Returns {cloned, output}.
        """
        url = repo_url.strip()
        if token and url.startswith("https://"):
            url = url.replace("https://", f"https://x-access-token:{token}@", 1)
        branch_arg = ""
        if branch and branch.strip():
            safe_branch = branch.strip().replace('"', "").replace("'", "").replace(" ", "")
            branch_arg = f'--branch "{safe_branch}" '
        # clone into the current directory (workspace root); the dir must be empty
        cmd = f'git clone --depth 1 {branch_arg}"{url}" .'
        result = await self.terminal.run(cmd, timeout=240)
        output = (result.stdout + result.stderr)
        if token:
            output = output.replace(token, "***")
        return {"cloned": result.ok, "output": output[-2000:]}

    async def status(self) -> str:
        result = await self.terminal.run("git status --short")
        return result.stdout.strip()

    async def log(self, limit: int = 10) -> str:
        result = await self.terminal.run(f"git log --oneline -n {limit}")
        return result.stdout.strip()

    async def _execute(self, input: ToolInput) -> ToolOutput:
        action = input.action
        params = input.parameters
        try:
            if action == "init":
                return ToolOutput(success=await self.init())
            if action == "commit":
                data = await self.commit_all(params.get("message", "Factory commit"))
                return ToolOutput(success=data["committed"], data=data)
            if action == "status":
                return ToolOutput(success=True, data=await self.status())
            if action == "log":
                return ToolOutput(success=True, data=await self.log(params.get("limit", 10)))
            return ToolOutput(success=False, error=f"Unknown action: {action}")
        except Exception as exc:  # noqa: BLE001
            return ToolOutput(success=False, error=str(exc))
