"""
Tests for the real tool layer + workspace.
These run fully offline (no DB, no network, no LLM).
"""
import pytest

from app.tools.filesystem_tool import FilesystemTool
from app.tools.terminal_tool import TerminalTool
from app.workspace import Workspace


def test_filesystem_write_read_roundtrip(tmp_path):
    fs = FilesystemTool(tmp_path)
    fs.write_file("src/index.html", "<!doctype html><html><body>hi</body></html>")
    assert fs.exists("src/index.html")
    assert "hi" in fs.read_file("src/index.html")
    files = fs.list_files()
    assert any(f["path"] == "src/index.html" for f in files)


def test_filesystem_blocks_path_traversal(tmp_path):
    fs = FilesystemTool(tmp_path)
    with pytest.raises(ValueError):
        fs.write_file("../escape.txt", "nope")
    with pytest.raises(ValueError):
        fs.write_file("../../etc/passwd", "nope")


@pytest.mark.asyncio
async def test_terminal_runs_command(tmp_path):
    term = TerminalTool(tmp_path)
    result = await term.run("echo factory-ok")
    assert result.ok
    assert "factory-ok" in result.stdout


@pytest.mark.asyncio
async def test_terminal_timeout(tmp_path):
    term = TerminalTool(tmp_path)
    result = await term.run("sleep 5", timeout=1)
    assert result.timed_out
    assert not result.ok


@pytest.mark.asyncio
async def test_workspace_materialize_and_verify(tmp_path):
    ws = Workspace("wf-test", root=str(tmp_path)).ensure()
    ws.write_files([
        {"name": "index.html", "content": "<!doctype html><html><body><div>App</div></body></html>"},
        {"name": "data.json", "content": '{"ok": true}'},
        {"name": "broken.json", "content": "{not valid json"},
    ])
    report = await ws.verify()
    checks = {c["file"]: c["ok"] for c in report["checks"]}
    assert checks["index.html"] is True
    assert checks["data.json"] is True
    assert checks["broken.json"] is False
    assert report["failed"] >= 1


@pytest.mark.asyncio
async def test_workspace_snapshot_reads_disk(tmp_path):
    ws = Workspace("wf-snap", root=str(tmp_path)).ensure()
    ws.write_files([{"name": "app.js", "content": "console.log('hello');"}])
    snapshot = ws.snapshot_as_files()
    names = {f["name"] for f in snapshot}
    assert "app.js" in names
    js = next(f for f in snapshot if f["name"] == "app.js")
    assert js["artifact_type"] == "javascript"
