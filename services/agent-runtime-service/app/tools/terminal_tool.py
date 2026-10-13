"""
Terminal Tool
Lets agents actually run shell commands inside the workspace sandbox
(build, lint, tests, syntax checks) with a hard timeout and captured output.
"""
import asyncio
import re
from pathlib import Path

from app.core.config import settings
from app.tools.base_tool import BaseTool, ToolInput, ToolOutput

MAX_OUTPUT = 20_000  # truncate captured stdout/stderr to keep payloads sane

# Commands the agent must never be allowed to run. This is a guardrail layer on
# top of (not a replacement for) real container/VM isolation.
_DENY_PATTERNS = [
    r"\brm\s+-rf\s+/(?!workspaces)",          # wiping the filesystem root
    r":\(\)\s*\{\s*:\|:&\s*\}\s*;",           # fork bomb
    r"\bmkfs\b", r"\bdd\s+if=", r"\bshutdown\b", r"\breboot\b",
    r">\s*/dev/sd", r"\bchmod\s+-R\s+777\s+/",
    r"\bsudo\b", r"\bsu\s+-",
    r"/etc/shadow", r"/etc/passwd",
    r"\bcurl\b[^|]*\|\s*(ba)?sh", r"\bwget\b[^|]*\|\s*(ba)?sh",  # curl|sh remote exec
    r"\b(nc|ncat|netcat)\b\s+-[le]",          # reverse/bind shells
]
_DENY_RE = [re.compile(p) for p in _DENY_PATTERNS]


def _blocked_reason(command: str) -> str | None:
    for pattern in _DENY_RE:
        if pattern.search(command):
            return f"Command blocked by security policy (matched: {pattern.pattern})"
    return None


def _apply_rlimits():  # runs in the child process just before exec (Linux only)
    try:
        import resource
        # CPU seconds, address space (1GB), max file size (50MB), max processes
        resource.setrlimit(resource.RLIMIT_CPU, (60, 90))
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    except Exception:
        pass  # resource limits are best-effort


class CommandResult:
    def __init__(self, command: str, exit_code: int, stdout: str, stderr: str, timed_out: bool = False):
        self.command = command
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> dict:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "ok": self.ok,
        }


class TerminalTool(BaseTool):
    tool_id = "terminal_tool"
    description = "Runs shell commands inside the workspace with a timeout and captured output."
    version = "1.0.0"

    def __init__(self, workspace_root: str | Path):
        super().__init__()
        self.root = Path(workspace_root).resolve()

    async def run(self, command: str, timeout: int | None = None) -> CommandResult:
        timeout = timeout or settings.TOOL_COMMAND_TIMEOUT

        blocked = _blocked_reason(command)
        if blocked:
            self.logger.warning("Blocked command", command=command, reason=blocked)
            return CommandResult(command, exit_code=126, stdout="", stderr=blocked)

        self.root.mkdir(parents=True, exist_ok=True)
        self.logger.info("Running command", command=command, cwd=str(self.root))
        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=str(self.root),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=_apply_rlimits,
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return CommandResult(command, exit_code=124, stdout="", stderr=f"Command timed out after {timeout}s", timed_out=True)

        stdout = stdout_b.decode(errors="replace")[:MAX_OUTPUT]
        stderr = stderr_b.decode(errors="replace")[:MAX_OUTPUT]
        return CommandResult(command, exit_code=proc.returncode or 0, stdout=stdout, stderr=stderr)

    async def which(self, binary: str) -> bool:
        result = await self.run(f"command -v {binary}", timeout=10)
        return result.ok

    async def _execute(self, input: ToolInput) -> ToolOutput:
        if input.action != "run":
            return ToolOutput(success=False, error=f"Unknown action: {input.action}")
        command = input.parameters.get("command")
        if not command:
            return ToolOutput(success=False, error="Missing 'command' parameter")
        result = await self.run(command, input.parameters.get("timeout"))
        return ToolOutput(success=result.ok, data=result.to_dict(), error=None if result.ok else result.stderr)
