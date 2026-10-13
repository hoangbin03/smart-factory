"""
Real deployment for the DevOps agent.

Takes the produced project in a workflow's workspace, containerises it, and runs
it as a live preview container on the host — returning a URL a human can open.

Architecture note: this runtime is itself a container. It talks to the HOST
Docker daemon through the mounted /var/run/docker.sock. The daemon cannot see
paths inside our mounted volume, so we never pass it a build-context path —
instead we stream the workspace as a tar over the Docker API
(`tar -c . | docker build -`). The product container is a sibling of this one
and publishes its port directly on the host, so the browser reaches it at
http://localhost:<port>.

Everything is gated behind settings.ENABLE_REAL_DEPLOY because mounting the
Docker socket grants real host access.
"""
import asyncio
import hashlib
import re
import shlex
from pathlib import Path
from typing import Any, Dict, Optional

import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Default container port per detected stack.
_STACK_PORT = {"static": 80, "node": 3000, "python": 8000, "custom": 80}

_NGINX_DOCKERFILE = """FROM nginx:alpine
COPY . /usr/share/nginx/html
RUN rm -f /usr/share/nginx/html/Dockerfile
EXPOSE 80
"""

_NODE_DOCKERFILE = """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --production || npm install || true
COPY . .
EXPOSE 3000
CMD ["sh", "-c", "npm start || node server.js || node index.js"]
"""

_PYTHON_DOCKERFILE = """FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt || true
EXPOSE 8000
CMD ["sh", "-c", "python main.py || python app.py || uvicorn main:app --host 0.0.0.0 --port 8000"]
"""


class Deployer:
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        short = (workflow_id.split("-")[0] or "wf")[:12]
        self.root = Path(settings.WORKSPACE_ROOT) / workflow_id
        name = f"{settings.DEPLOY_IMAGE_PREFIX}-{short}".lower()
        self.image = name
        self.container = name

    # ── stack detection ──────────────────────────────────────────
    def _all_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        return [p for p in self.root.rglob("*") if p.is_file() and ".git" not in p.parts]

    def detect_stack(self) -> str:
        names = {p.name.lower() for p in self._all_files()}
        if "dockerfile" in names:
            return "custom"
        if "package.json" in names:
            return "node"
        if "requirements.txt" in names or any(n.endswith(".py") for n in names):
            return "python"
        return "static"  # default: serve files statically via nginx

    def _dockerfile_expose(self, text: str) -> Optional[int]:
        m = re.search(r"^\s*EXPOSE\s+(\d+)", text, flags=re.MULTILINE | re.IGNORECASE)
        return int(m.group(1)) if m else None

    def ensure_dockerfile(self, stack: str) -> int:
        """Make sure the workspace has a Dockerfile. Returns the container port."""
        df = self.root / "Dockerfile"
        if df.exists():
            text = df.read_text(encoding="utf-8", errors="replace")
            return self._dockerfile_expose(text) or _STACK_PORT.get(stack, 80)
        content = {
            "static": _NGINX_DOCKERFILE,
            "node": _NODE_DOCKERFILE,
            "python": _PYTHON_DOCKERFILE,
        }.get(stack, _NGINX_DOCKERFILE)
        df.write_text(content, encoding="utf-8")
        return self._dockerfile_expose(content) or _STACK_PORT.get(stack, 80)

    def _pick_host_port(self) -> int:
        span = max(1, settings.DEPLOY_PORT_MAX - settings.DEPLOY_PORT_MIN + 1)
        h = int(hashlib.sha1(self.workflow_id.encode()).hexdigest(), 16)
        return settings.DEPLOY_PORT_MIN + (h % span)

    # ── shell helper ─────────────────────────────────────────────
    async def _run(self, cmd: str, stdin: Optional[bytes] = None, timeout: int = 300) -> tuple[int, str]:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdin=asyncio.subprocess.PIPE if stdin is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(stdin), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, f"command timed out after {timeout}s: {cmd[:80]}"
        return proc.returncode, (out or b"").decode("utf-8", errors="replace")

    # ── main API ─────────────────────────────────────────────────
    async def deploy(self) -> Dict[str, Any]:
        if not settings.ENABLE_REAL_DEPLOY:
            return {"ok": False, "disabled": True, "error": "Real deploy is disabled (ENABLE_REAL_DEPLOY=false)."}
        if not self.root.exists() or not self._all_files():
            return {"ok": False, "error": "No workspace files to deploy."}

        stack = self.detect_stack()
        container_port = self.ensure_dockerfile(stack)
        host_port = self._pick_host_port()

        # 1) Build: stream the workspace as a tar context over the Docker API.
        build_cmd = (
            f"tar -C {shlex.quote(str(self.root))} --exclude=./.git --exclude=./__pycache__ -c . "
            f"| docker build -t {self.image} -"
        )
        rc, out = await self._run(build_cmd, timeout=600)
        if rc != 0:
            logger.error("Deploy build failed", workflow_id=self.workflow_id, rc=rc)
            return {"ok": False, "stage": "build", "stack": stack, "error": out[-2000:]}

        # 2) Replace any previous preview container for this workflow.
        await self._run(f"docker rm -f {self.container}", timeout=60)

        # 3) Run the product as a detached sibling publishing its port on the host.
        run_cmd = (
            f"docker run -d --name {self.container} "
            f"--label factory.workflow={self.workflow_id} "
            f"-p {host_port}:{container_port} {self.image}"
        )
        rc, out = await self._run(run_cmd, timeout=120)
        if rc != 0:
            return {"ok": False, "stage": "run", "stack": stack, "error": out[-2000:]}

        url = f"http://{settings.DEPLOY_HOST}:{host_port}"

        # 4) Best-effort readiness probe via the host gateway, then grab logs.
        await asyncio.sleep(3)
        probe_rc, _ = await self._run(
            f"curl -fsS -o /dev/null -m 5 http://host.docker.internal:{host_port}/", timeout=15
        )
        _, logs = await self._run(f"docker logs --tail 25 {self.container}", timeout=30)

        return {
            "ok": True,
            "url": url,
            "port": host_port,
            "container_port": container_port,
            "image": self.image,
            "container": self.container,
            "stack": stack,
            "reachable": probe_rc == 0,
            "logs": (logs or "")[-1500:],
        }

    async def undeploy(self) -> Dict[str, Any]:
        rc, out = await self._run(f"docker rm -f {self.container}", timeout=60)
        return {"ok": rc == 0, "output": out.strip()[-500:]}
