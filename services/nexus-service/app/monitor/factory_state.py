"""Database-backed factory state for Nexus."""
from typing import Any, Dict

from sqlalchemy import text

from app.core.database import get_session


async def load_factory_state() -> Dict[str, Any]:
    """Load current workflow, task, and agent state from Postgres."""
    async with get_session() as session:
        workflow_counts = await session.execute(text("""
            SELECT status::text AS status, COUNT(*)::int AS count
            FROM workflows
            GROUP BY status
        """))
        workflow_by_status = {
            row["status"]: row["count"]
            for row in workflow_counts.mappings().all()
        }

        workflows = await session.execute(text("""
            SELECT
                w.id::text AS id,
                w.name,
                w.description,
                w.status::text AS status,
                w.goal,
                w.created_at,
                w.started_at,
                w.completed_at,
                COUNT(t.id)::int AS task_count,
                (COUNT(t.id) FILTER (WHERE t.status = 'COMPLETED'))::int AS tasks_completed,
                (COUNT(t.id) FILTER (WHERE t.status = 'FAILED'))::int AS tasks_failed,
                (COUNT(t.id) FILTER (WHERE t.status = 'RUNNING'))::int AS tasks_running,
                (COUNT(t.id) FILTER (WHERE t.status = 'PENDING'))::int AS tasks_pending
            FROM workflows w
            LEFT JOIN tasks t ON t.workflow_id = w.id
            GROUP BY w.id
            ORDER BY w.created_at DESC
            LIMIT 25
        """))
        workflow_rows = [dict(row) for row in workflows.mappings().all()]

        task_counts = await session.execute(text("""
            SELECT status::text AS status, COUNT(*)::int AS count
            FROM tasks
            GROUP BY status
        """))
        task_by_status = {
            row["status"]: row["count"]
            for row in task_counts.mappings().all()
        }

        recent_tasks = await session.execute(text("""
            SELECT
                id::text AS id,
                workflow_id::text AS workflow_id,
                name,
                status::text AS status,
                agent_id,
                goal,
                "order",
                retry_count,
                max_retries,
                updated_at,
                started_at,
                completed_at
            FROM tasks
            ORDER BY updated_at DESC
            LIMIT 50
        """))
        task_rows = [dict(row) for row in recent_tasks.mappings().all()]

        agents = await session.execute(text("""
            SELECT
                a.agent_id,
                a.name,
                a.role,
                a.runtime,
                a.status::text AS status,
                a.last_seen_at,
                COUNT(t.id)::int AS total_tasks,
                (COUNT(t.id) FILTER (WHERE t.status = 'COMPLETED'))::int AS completed_tasks,
                (COUNT(t.id) FILTER (WHERE t.status = 'FAILED'))::int AS failed_tasks,
                (COUNT(t.id) FILTER (WHERE t.status = 'RUNNING'))::int AS running_tasks
            FROM agents a
            LEFT JOIN tasks t ON t.agent_id = a.agent_id
            GROUP BY a.id
            ORDER BY a.role, a.agent_id
        """))
        agent_rows = [dict(row) for row in agents.mappings().all()]

    active_statuses = {"PENDING", "RUNNING", "PAUSED"}
    active_workflows = sum(
        count for status, count in workflow_by_status.items()
        if status in active_statuses
    )

    return {
        "workflows": {
            "total": sum(workflow_by_status.values()),
            "active": active_workflows,
            "by_status": workflow_by_status,
            "list": workflow_rows,
        },
        "tasks": {
            "total": sum(task_by_status.values()),
            "by_status": task_by_status,
            "list": task_rows,
        },
        "agents": {
            "total": len(agent_rows),
            "list": agent_rows,
        },
    }


async def load_nexus_snapshot(event_snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Merge live event memory with authoritative database state."""
    db_state = await load_factory_state()
    snapshot = dict(event_snapshot)
    snapshot["database"] = db_state
    snapshot["workflows"] = db_state["workflows"]
    snapshot["tasks"] = db_state["tasks"]
    snapshot["agents"] = db_state["agents"]
    return snapshot
