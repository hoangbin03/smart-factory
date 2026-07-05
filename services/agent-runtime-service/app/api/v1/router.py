from fastapi import APIRouter

api_router = APIRouter()

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
