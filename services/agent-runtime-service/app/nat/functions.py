"""
Factory tool layer exposed as NVIDIA NeMo Agent Toolkit (NAT) functions.

Each function is registered with NAT via @register_function and is sandboxed to
a single workflow's Workspace (the workflow_id is baked into the function config
at build time). The NAT ReAct agent selects and calls these by name.
"""
from pydantic import BaseModel, Field

from nat.builder.function_info import FunctionInfo
from nat.cli.register_workflow import register_function
from nat.data_models.function import FunctionBaseConfig

from app.workspace import Workspace


# ── Write file ──────────────────────────────────────────────
class WriteFileConfig(FunctionBaseConfig, name="factory_write_file"):
    workflow_id: str


@register_function(config_type=WriteFileConfig)
async def factory_write_file(config: WriteFileConfig, builder):
    ws = Workspace(config.workflow_id).ensure()

    class WriteFileInput(BaseModel):
        path: str = Field(description="Relative file path inside the project, e.g. index.html or src/app.js")
        content: str = Field(description="The complete text content to write to the file")

    async def _write(path: str, content: str) -> str:
        ws.fs.write_file(path, content)
        return f"Wrote {path} ({len(content)} bytes) to the workspace."

    yield FunctionInfo.from_fn(
        _write,
        input_schema=WriteFileInput,
        description="Write a complete text file into the project workspace on disk. Overwrites if it exists.",
    )


# ── Read file ───────────────────────────────────────────────
class ReadFileConfig(FunctionBaseConfig, name="factory_read_file"):
    workflow_id: str


@register_function(config_type=ReadFileConfig)
async def factory_read_file(config: ReadFileConfig, builder):
    ws = Workspace(config.workflow_id).ensure()

    class ReadFileInput(BaseModel):
        path: str = Field(description="Relative path of the file to read")

    async def _read(path: str) -> str:
        try:
            return ws.fs.read_file(path)[:8000]
        except Exception as exc:  # noqa: BLE001
            return f"ERROR reading {path}: {exc}"

    yield FunctionInfo.from_fn(
        _read, input_schema=ReadFileInput,
        description="Read the contents of a file from the project workspace.",
    )


# ── List files ──────────────────────────────────────────────
class ListFilesConfig(FunctionBaseConfig, name="factory_list_files"):
    workflow_id: str


@register_function(config_type=ListFilesConfig)
async def factory_list_files(config: ListFilesConfig, builder):
    ws = Workspace(config.workflow_id).ensure()

    class ListFilesInput(BaseModel):
        pass

    async def _list(*_args, **_kwargs) -> str:
        files = ws.list_files()
        if not files:
            return "The workspace is empty."
        return "\n".join(f"{f['path']} ({f['size']}b)" for f in files)

    yield FunctionInfo.from_fn(
        _list, input_schema=ListFilesInput,
        description="List all files currently in the project workspace.",
    )


# ── Run shell command ───────────────────────────────────────
class RunCommandConfig(FunctionBaseConfig, name="factory_run_command"):
    workflow_id: str


@register_function(config_type=RunCommandConfig)
async def factory_run_command(config: RunCommandConfig, builder):
    ws = Workspace(config.workflow_id).ensure()

    class RunCommandInput(BaseModel):
        command: str = Field(description="Shell command to run in the workspace, e.g. 'node --check script.js' or 'ls -la'")

    async def _run(command: str) -> str:
        result = await ws.terminal.run(command, timeout=60)
        return f"exit_code={result.exit_code}\nstdout:\n{result.stdout[:1500]}\nstderr:\n{result.stderr[:600]}"

    yield FunctionInfo.from_fn(
        _run, input_schema=RunCommandInput,
        description="Run a shell command inside the project workspace to build, verify, or inspect the code.",
    )


# The tool names the ReAct developer agent is allowed to use.
DEVELOPER_TOOL_NAMES = [
    "factory_write_file",
    "factory_read_file",
    "factory_list_files",
    "factory_run_command",
]
