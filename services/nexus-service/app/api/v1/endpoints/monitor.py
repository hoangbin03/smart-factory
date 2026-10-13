"""Nexus Monitor endpoints — factory state, events, stats."""
from fastapi import APIRouter, Query
from typing import Optional
from app.monitor.event_aggregator import aggregator
from app.monitor.factory_state import load_nexus_snapshot

router = APIRouter()


@router.get("/snapshot")
async def get_snapshot():
    """Full factory state snapshot."""
    return await load_nexus_snapshot(aggregator.snapshot())


@router.get("/events")
async def get_events(limit: int = Query(50, le=500)):
    """Recent events (ring buffer)."""
    events = list(aggregator._events)[:limit]
    return {"events": events, "total": aggregator.total_events}


@router.get("/stats")
async def get_stats():
    """High-level factory statistics."""
    snap = await load_nexus_snapshot(aggregator.snapshot())
    wfs = snap["workflows"]["list"]
    tasks = snap["tasks"]["list"]
    agents = snap["agents"]["list"]

    running = sum(1 for w in wfs if w.get("status") == "RUNNING")
    completed = sum(1 for w in wfs if w.get("status") == "COMPLETED")
    failed = sum(1 for w in wfs if w.get("status") == "FAILED")

    return {
        "workflows": {"total": snap["workflows"]["total"], "running": running, "completed": completed, "failed": failed},
        "tasks": {"total": snap["tasks"]["total"]},
        "agents": {"total": snap["agents"]["total"]},
        "events_processed": snap["total_events"],
    }
