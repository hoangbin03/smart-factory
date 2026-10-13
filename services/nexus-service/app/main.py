"""
Nexus Service — Master Intelligence Agent
Monitors all agents, projects, workflows in real-time.
Provides WebSocket broadcast, chat interface, and summary API.
"""
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import init_db, get_session
from app.core.nats_client import nats_client
from app.core.agent_config import load_agent_ai_config
from app.core.llm_client import llm_config_context, llm_client
from app.monitor.event_aggregator import aggregator
from app.monitor.factory_state import load_nexus_snapshot, load_factory_state
from app.api.v1.router import api_router

logger = structlog.get_logger()

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active: List[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.active.append(ws)
        logger.info("WS client connected", total=len(self.active))

    def disconnect(self, ws: WebSocket):
        if ws in self.active:
            self.active.remove(ws)
        logger.info("WS client disconnected", total=len(self.active))

    async def broadcast(self, data: Dict[str, Any]):
        payload = json.dumps(data, default=str)
        dead = []
        for ws in self.active:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)

ws_manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🌌 Nexus Service starting...")
    await init_db()
    await nats_client.connect()

    # Subscribe to ALL factory events
    async def on_event(msg):
        try:
            data = json.loads(msg.data.decode())
            subject = msg.subject
            event = aggregator.ingest(subject, data)
            await ws_manager.broadcast({"type": "event", "subject": subject, "data": event})
        except Exception as e:
            logger.error("Nexus event handler error", error=str(e))

    await nats_client.subscribe("runtime.agent.*", on_event)
    await nats_client.subscribe("workflow.*", on_event)
    await nats_client.subscribe("task.*", on_event)
    await nats_client.subscribe("audit.*", on_event)
    await nats_client.subscribe("factory.workflow.*", on_event)
    await nats_client.subscribe("factory.task.*", on_event)
    await nats_client.subscribe("factory.audit.*", on_event)

    logger.info("✅ Nexus Service ready — monitoring all factory events")
    yield
    logger.info("🛑 Nexus shutting down...")
    await nats_client.disconnect()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Nexus — Smart Factory Master Intelligence",
        description="Real-time monitor, knowledge aggregator and chat interface for Smart Factory",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    import os
    allowed = [o.strip() for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:8080,http://127.0.0.1:8080"
    ).split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix="/api/v1")

    @app.get("/health", tags=["health"])
    async def health():
        return {
            "status": "healthy",
            "service": "nexus-service",
            "identity": "Nexus — Smart Factory Master Intelligence",
            "connections": len(ws_manager.active),
            "events_processed": aggregator.total_events,
        }

    @app.websocket("/ws/monitor")
    @app.websocket("/api/v1/monitor/ws/monitor")
    async def ws_monitor(ws: WebSocket):
        """Real-time event stream for the monitor dashboard."""
        await ws_manager.connect(ws)
        # Send current state snapshot
        snapshot = await load_nexus_snapshot(aggregator.snapshot())
        await ws.send_text(json.dumps({"type": "snapshot", "data": snapshot}, default=str))
        try:
            while True:
                # Keep connection alive, listen for ping
                await ws.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(ws)

    @app.websocket("/ws/chat")
    @app.websocket("/api/v1/monitor/ws/chat")
    async def ws_chat(ws: WebSocket):
        """Chat with Nexus — Retrieval-Augmented conversation."""
        await ws.accept()
        session_id = str(uuid.uuid4())
        history: List[Dict] = []

        await ws.send_text(json.dumps({
            "type": "welcome",
            "message": "Tôi là Nexus — AI Master của Smart Factory. Tôi nắm mọi hoạt động của factory. Hỏi tôi bất cứ điều gì.",
            "session_id": session_id,
        }))

        try:
            while True:
                raw = await ws.receive_text()
                payload = json.loads(raw)
                user_msg = payload.get("message", "")
                history.append({"role": "user", "content": user_msg})

                ctx = await load_nexus_snapshot(aggregator.snapshot())
                db_state = await load_factory_state()
                context_str = json.dumps(
                    {"live_events": ctx, "database_state": db_state},
                    default=str,
                    indent=2,
                )[:6000]

                system_prompt = f"""Bạn là Nexus — Master Intelligence Agent của Smart Software Factory.
Bạn theo dõi TẤT CẢ các hoạt động: workflows, agents, tasks, dự án.
Bạn có quyền truy cập vào trạng thái thực của factory hiện tại.
Trả lời bằng tiếng Việt nếu người dùng hỏi tiếng Việt.

FACTORY STATE (realtime):
{context_str}

Hãy trả lời chính xác, ngắn gọn, dựa trên dữ liệu thực tế."""

                user_prompt = "\n".join([
                    f"{m['role'].upper()}: {m['content']}" for m in history[-6:]
                ])

                ai_config = await load_agent_ai_config("nexus_agent")
                with llm_config_context(ai_config):
                    reply = await llm_client.complete(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        temperature=0.3,
                    )

                history.append({"role": "assistant", "content": reply})
                await ws.send_text(json.dumps({
                    "type": "reply",
                    "message": reply,
                    "session_id": session_id,
                }))
        except WebSocketDisconnect:
            logger.info("Nexus chat session ended", session=session_id)

    return app


app = create_app()
