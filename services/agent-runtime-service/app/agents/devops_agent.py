"""
DevOps Agent
Manages deployments, containers, and infrastructure.
Tools: Docker Tool, Kubernetes Tool
"""
from typing import Any
from app.agents.llm_agent import LLMAgent
from app.agents.base_agent import AgentTaskInput, AgentTaskOutput, AgentArtifact
from app.core.llm_client import llm_client


class DevOpsAgent(LLMAgent):
    agent_id = "devops_agent"
    role = "devops"
    version = "1.0.0"

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
        # Generate deployment config
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

        # Generate monitoring config
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
            "steps": len(plan),
        }

    async def report(
        self,
        task: AgentTaskInput,
        result: dict[str, Any],
        reflection: str,
    ) -> AgentTaskOutput:
        return AgentTaskOutput(
            success=True,
            summary=f"Deployment configuration created for: {task.goal}",
            artifacts=[
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
            ],
            metrics={"configs_generated": 2},
        )
