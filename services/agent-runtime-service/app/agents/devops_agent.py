"""
DevOps Agent
Manages deployments, containers, and infrastructure.
When ENABLE_REAL_DEPLOY is on, it actually containerises the product in the
workflow workspace and runs it as a live preview container, returning a URL.
Otherwise (and always, as documentation) it generates deployment config.
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client
from app.core.config import settings


class DevOpsAgent(LLMAgent):
    agent_id = "devops_agent"
    role = "devops"
    version = "2.0.0"

    SYSTEM_PROMPT = """You are a Senior DevOps/Platform Engineer in the Factory Platform.
Your responsibilities:
- Design CI/CD pipelines
- Write Dockerfiles and Docker Compose configurations
- Create Kubernetes manifests (Deployment, Service, Ingress, HPA)
- Set up monitoring and alerting (Prometheus, Grafana)
- Infrastructure as Code (Terraform, Helm)
- Security hardening

Output: Always produce working, production-ready infrastructure code."""

    async def run(self, task: AgentTaskInput, plan: list[str]) -> dict[str, Any]:
        # 1) REAL DEPLOY: build & run the product as a live container (if enabled).
        deployment_result: dict[str, Any] | None = None
        if settings.ENABLE_REAL_DEPLOY:
            try:
                from app.deploy import Deployer
                deployment_result = await Deployer(task.ws).deploy()
                self.logger.info("Real deploy finished", ok=deployment_result.get("ok"),
                                 url=deployment_result.get("url"))
            except Exception as exc:  # noqa: BLE001 — never crash the pipeline on deploy failure
                self.logger.error("Real deploy crashed", error=str(exc))
                deployment_result = {"ok": False, "error": str(exc)}

        # 2) Deployment config (documentation / IaC), always produced.
        deployment = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create deployment configuration for:
Goal: {task.goal}
Context: {task.context}

Produce:
1. Dockerfile (multi-stage)
2. docker-compose.yml
3. Kubernetes Deployment YAML
4. Kubernetes Service YAML
5. CI/CD Pipeline (GitHub Actions)""",
        )

        # 3) Monitoring config.
        monitoring = await llm_client.complete(
            system_prompt=self.SYSTEM_PROMPT,
            user_prompt=f"""Create monitoring setup for: {task.goal}
Produce:
1. Prometheus metrics configuration
2. Grafana dashboard JSON
3. Alert rules
4. Health check endpoints""",
        )

        return {
            "output": deployment,
            "monitoring": monitoring,
            "deployment_result": deployment_result,
            "steps": len(plan),
        }

    def _render_deploy_report(self, task: AgentTaskInput, deploy: dict[str, Any] | None) -> str:
        if not deploy:
            return (
                f"# Deployment — {task.goal}\n\n"
                "_Real deployment is disabled (ENABLE_REAL_DEPLOY=false). "
                "Set it to true and mount the Docker socket to get a live preview URL._"
            )
        if not deploy.get("ok"):
            return (
                f"# Deployment FAILED — {task.goal}\n\n"
                f"- Stage: `{deploy.get('stage', 'n/a')}`\n"
                f"- Stack: `{deploy.get('stack', 'n/a')}`\n\n"
                f"```\n{deploy.get('error', 'unknown error')[:1200]}\n```"
            )
        return "\n".join([
            f"# Deployment LIVE — {task.goal}",
            "",
            f"- **Preview URL:** {deploy.get('url')}",
            f"- Reachable: {'✅ yes' if deploy.get('reachable') else '⏳ starting (may need a few seconds)'}",
            f"- Stack: `{deploy.get('stack')}`",
            f"- Image: `{deploy.get('image')}`",
            f"- Container: `{deploy.get('container')}`  (host {deploy.get('port')} → container {deploy.get('container_port')})",
            "",
            "## Container logs (tail)",
            "```",
            (deploy.get("logs") or "(no logs)").strip(),
            "```",
        ])

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        deploy = result.get("deployment_result")
        deployed_ok = bool(deploy and deploy.get("ok"))
        preview_url = deploy.get("url") if deployed_ok else None

        artifacts = [
            AgentArtifact(
                artifact_type="deployment_config",
                name="deployment.md",
                content=result.get("output", ""),
            ),
            AgentArtifact(
                artifact_type="monitoring_config",
                name="monitoring.md",
                content=result.get("monitoring", ""),
            ),
            AgentArtifact(
                artifact_type="deployment_report",
                name="deployment_report.md",
                content=self._render_deploy_report(task, deploy),
                metadata={"preview_url": preview_url, "deployed": deployed_ok},
            ),
        ]

        if deployed_ok:
            summary = f"Deployed live for '{task.goal}' → {preview_url}"
        elif deploy and not deploy.get("disabled"):
            summary = f"Deployment attempted but FAILED for '{task.goal}' (see deployment_report.md)"
        else:
            summary = f"Deployment configuration created for: {task.goal}"

        return AgentTaskOutput(
            success=True,
            summary=summary,
            artifacts=artifacts,
            metrics={
                "configs_generated": 2,
                "deployed": deployed_ok,
                "preview_url": preview_url,
            },
            next_action=f"Open preview: {preview_url}" if preview_url else "Review deployment config",
        )
