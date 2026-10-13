import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.config import settings

api_router = APIRouter()


class PushRequest(BaseModel):
    remote_url: str
    token: str = ""
    branch: str = "main"


class GitImportRequest(BaseModel):
    repo_url: str
    branch: str = ""
    token: str = ""


class UploadFile(BaseModel):
    path: str
    content: str


class UploadImportRequest(BaseModel):
    files: list[UploadFile]
    replace: bool = True


def _validate_workflow_id(workflow_id: str) -> None:
    if "/" in workflow_id or "\\" in workflow_id or ".." in workflow_id:
        raise HTTPException(400, "Invalid workflow id")


@api_router.post("/workspace/{workflow_id}/import/git")
async def import_git(workflow_id: str, body: GitImportRequest):
    """Clone a remote git repo into the workflow workspace so agents can work on it."""
    _validate_workflow_id(workflow_id)
    if not body.repo_url.strip():
        raise HTTPException(400, "repo_url is required")
    from app.workspace import Workspace
    result = await Workspace(workflow_id).import_from_git(body.repo_url, body.branch, body.token)
    if not result.get("ok"):
        raise HTTPException(502, f"Clone failed: {result.get('output', result.get('error', ''))[-500:]}")
    return result


@api_router.post("/workspace/{workflow_id}/import/upload")
async def import_upload(workflow_id: str, body: UploadImportRequest):
    """Import an uploaded local folder ({path, content} files) into the workspace."""
    _validate_workflow_id(workflow_id)
    if not body.files:
        raise HTTPException(400, "No files provided")
    from app.workspace import Workspace
    result = Workspace(workflow_id).import_files(
        [f.model_dump() for f in body.files], replace=body.replace,
    )
    if not result.get("ok"):
        raise HTTPException(400, "No importable files (all skipped)")
    return result


@api_router.post("/workspace/{workflow_id}/push")
async def push_workspace(workflow_id: str, body: PushRequest):
    """Publish the produced project to a Git remote (e.g. GitHub) using a provided token."""
    if "/" in workflow_id or "\\" in workflow_id or ".." in workflow_id:
        raise HTTPException(400, "Invalid workflow id")
    from app.workspace import Workspace
    ws = Workspace(workflow_id)
    if not ws.path.exists():
        raise HTTPException(404, "No workspace for this workflow")
    result = await ws.git.push_to_remote(body.remote_url, body.token, body.branch)
    if not result.get("pushed"):
        raise HTTPException(502, f"Push failed: {result.get('output', '')[-500:]}")
    return {"pushed": True, "branch": body.branch}


@api_router.post("/workspace/{workflow_id}/deploy")
async def deploy_workspace(workflow_id: str):
    """Build & run the produced project as a live preview container. Returns the URL."""
    if "/" in workflow_id or "\\" in workflow_id or ".." in workflow_id:
        raise HTTPException(400, "Invalid workflow id")
    from app.deploy import Deployer
    result = await Deployer(workflow_id).deploy()
    if not result.get("ok"):
        raise HTTPException(502, result.get("error", "Deploy failed"))
    return result


@api_router.post("/workspace/{workflow_id}/undeploy")
async def undeploy_workspace(workflow_id: str):
    """Stop and remove the workflow's preview container."""
    if "/" in workflow_id or "\\" in workflow_id or ".." in workflow_id:
        raise HTTPException(400, "Invalid workflow id")
    from app.deploy import Deployer
    return await Deployer(workflow_id).undeploy()


@api_router.get("/workspace/{workflow_id}/download")
async def download_workspace(workflow_id: str):
    """Zip the produced project (the workflow's workspace) and stream it for download."""
    # workflow_id is a UUID from the DB; reject anything that could escape the root
    if "/" in workflow_id or "\\" in workflow_id or ".." in workflow_id:
        raise HTTPException(400, "Invalid workflow id")
    root = (Path(settings.WORKSPACE_ROOT) / workflow_id).resolve()
    if not str(root).startswith(str(Path(settings.WORKSPACE_ROOT).resolve())) or not root.exists():
        raise HTTPException(404, "No workspace for this workflow")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(root.rglob("*")):
            if path.is_file() and ".git" not in path.parts and "__pycache__" not in path.parts:
                zf.write(path, path.relative_to(root).as_posix())
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="workflow-{workflow_id}.zip"'},
    )


@api_router.get("/agents")
async def list_agents():
    """List all agents registered in this runtime instance."""
    from app.agents.architect_agent import ArchitectAgent
    from app.agents.planner_agent import PlannerAgent
    from app.agents.developer_agent import DeveloperAgent
    from app.agents.reviewer_agent import ReviewerAgent
    from app.agents.qa_agent import QAAgent
    from app.agents.devops_agent import DevOpsAgent
    
    return {
        "agents": [
            {
                "agent_id": ArchitectAgent.agent_id,
                "role": ArchitectAgent.role,
                "version": ArchitectAgent.version
            },
            {
                "agent_id": PlannerAgent.agent_id,
                "role": PlannerAgent.role,
                "version": PlannerAgent.version
            },
            {
                "agent_id": DeveloperAgent.agent_id,
                "role": DeveloperAgent.role,
                "version": DeveloperAgent.version
            },
            {
                "agent_id": ReviewerAgent.agent_id,
                "role": ReviewerAgent.role,
                "version": ReviewerAgent.version
            },
            {
                "agent_id": QAAgent.agent_id,
                "role": QAAgent.role,
                "version": QAAgent.version
            },
            {
                "agent_id": DevOpsAgent.agent_id,
                "role": DevOpsAgent.role,
                "version": DevOpsAgent.version
            }
        ]
    }
