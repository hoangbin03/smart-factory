"""Nexus API v1 Router."""
from fastapi import APIRouter
from app.api.v1.endpoints import monitor, agents, projects, chat, tools, skills

api_router = APIRouter()
api_router.include_router(monitor.router, prefix="/monitor", tags=["monitor"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
