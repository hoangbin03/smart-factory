"""Event Aggregator — Nexus collects and aggregates all factory events."""
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any, Dict, List


class EventAggregator:
    """
    Central memory for Nexus.
    Ingests events from NATS, maintains a live snapshot of the factory state.
    """

    MAX_EVENTS = 500  # ring buffer

    def __init__(self):
        self.total_events: int = 0
        self._events: deque = deque(maxlen=self.MAX_EVENTS)
        self._workflows: Dict[str, Dict] = {}
        self._tasks: Dict[str, Dict] = {}
        self._agents: Dict[str, Dict] = {}
        self._agent_stats: Dict[str, Dict] = defaultdict(lambda: {
            "total_tasks": 0, "success": 0, "failed": 0, "last_active": None
        })

    def ingest(self, subject: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process one event and update state."""
        self.total_events += 1
        now = datetime.now(timezone.utc).isoformat()

        event = {
            "id": self.total_events,
            "subject": subject,
            "timestamp": now,
            "data": data,
        }
        self._events.appendleft(event)

        # Update derived state
        self._update_state(subject, data)
        return event

    def _update_state(self, subject: str, data: Dict[str, Any]):
        now = datetime.now(timezone.utc).isoformat()

        if "workflow" in subject:
            wf_id = data.get("workflowId") or data.get("id")
            if wf_id:
                if wf_id not in self._workflows:
                    self._workflows[wf_id] = {}
                self._workflows[wf_id].update({
                    "id": wf_id,
                    "name": data.get("name", ""),
                    "status": data.get("status") or data.get("currentStatus", "UNKNOWN"),
                    "goal": data.get("goal", ""),
                    "updated_at": now,
                })

        elif "task" in subject:
            t_id = data.get("taskId") or data.get("id")
            if t_id:
                if t_id not in self._tasks:
                    self._tasks[t_id] = {}
                self._tasks[t_id].update({
                    "id": t_id,
                    "workflow_id": data.get("workflowId"),
                    "agent_id": data.get("agentId"),
                    "status": data.get("status") or data.get("currentStatus", "UNKNOWN"),
                    "updated_at": now,
                })

        elif "agent" in subject:
            agent_id = data.get("agentId") or data.get("agent_id")
            if agent_id:
                stats = self._agent_stats[agent_id]
                stats["last_active"] = now
                if "result" in subject:
                    stats["total_tasks"] += 1
                    if data.get("success"):
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                if agent_id not in self._agents:
                    self._agents[agent_id] = {}
                self._agents[agent_id].update({
                    "id": agent_id,
                    "status": "ACTIVE" if "result" in subject else "RUNNING",
                    "stats": stats,
                    "last_event": subject,
                    "updated_at": now,
                })

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of the factory."""
        recent_events = list(self._events)[:50]
        active_workflows = [w for w in self._workflows.values() if w.get("status") in ("RUNNING", "PENDING")]
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_events": self.total_events,
            "workflows": {
                "total": len(self._workflows),
                "active": len(active_workflows),
                "list": list(self._workflows.values())[-20:],
            },
            "tasks": {
                "total": len(self._tasks),
                "list": list(self._tasks.values())[-20:],
            },
            "agents": {
                "total": len(self._agents),
                "list": list(self._agents.values()),
            },
            "recent_events": recent_events,
        }

# Global instance
aggregator = EventAggregator()
