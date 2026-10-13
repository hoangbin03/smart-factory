"""
Agent long-term memory, backed by the KBS (RAG) service.

Before an agent works, it retrieves knowledge relevant to the goal from the
shared "factory-memory" collection (past architecture decisions, reviews, QA
findings, ...). After it finishes, it persists a compact record of what it did.
This makes the factory accumulate institutional knowledge across workflows
instead of every task starting blind.

All calls are best-effort: if KBS is unavailable the agent still runs, it just
loses the memory boost. Nothing here may raise into the agent lifecycle.
"""
from typing import Any

import httpx
import structlog

from app.core.config import settings

logger = structlog.get_logger()

MEMORY_COLLECTION = "factory-memory"
# Chroma cosine similarity score below this is treated as noise.
_MIN_SCORE = 0.15


class MemoryClient:
    def __init__(self) -> None:
        self._base = settings.KBS_URL.rstrip("/")

    async def retrieve(self, query: str, workflow_id: str = "", top_k: int | None = None) -> str:
        """Return a formatted knowledge block relevant to `query`, or '' if none."""
        if not settings.ENABLE_AGENT_MEMORY or not query or not query.strip():
            return ""
        k = top_k or settings.MEMORY_TOP_K
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.post(
                    f"{self._base}/api/v1/query",
                    json={
                        "query": query[:1000],
                        "collection": MEMORY_COLLECTION,
                        "top_k": k,
                        "with_answer": False,
                    },
                )
            if resp.status_code != 200:
                return ""
            chunks = resp.json().get("chunks", []) or []
        except Exception as exc:  # noqa: BLE001 — memory is best-effort
            logger.warning("Memory retrieve failed", error=str(exc))
            return ""

        picked = [c for c in chunks if c.get("score", 0) >= _MIN_SCORE][:k]
        if not picked:
            return ""

        lines = []
        for c in picked:
            meta = c.get("metadata", {}) or {}
            label = meta.get("title") or meta.get("source") or "note"
            text = str(c.get("text", "")).strip().replace("\n", " ")
            if text:
                lines.append(f"- ({label}) {text[:600]}")
        if not lines:
            return ""
        return (
            "RELEVANT KNOWLEDGE FROM THE FACTORY'S PAST WORK "
            "(reuse what helps, ignore what doesn't):\n" + "\n".join(lines)
        )

    async def remember(
        self,
        content: str,
        *,
        workflow_id: str,
        agent_id: str,
        goal: str,
    ) -> None:
        """Persist a compact record of an agent's output into the shared memory."""
        if not settings.ENABLE_AGENT_MEMORY or not content or not content.strip():
            return
        title = f"{agent_id} · {goal[:80]}"
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # KBS /documents ingests form fields (text/title/collection/tags)
                await client.post(
                    f"{self._base}/api/v1/documents",
                    data={
                        "text": content[:6000],
                        "title": title,
                        "collection": MEMORY_COLLECTION,
                        "tags": f"{agent_id},workflow:{workflow_id}",
                    },
                )
        except Exception as exc:  # noqa: BLE001 — memory is best-effort
            logger.warning("Memory remember failed", agent_id=agent_id, error=str(exc))

    @staticmethod
    def summarize_output(output: Any) -> str:
        """Build a compact, retrieval-friendly memory record from an agent output."""
        try:
            summary = getattr(output, "summary", "") or ""
            artifacts = getattr(output, "artifacts", []) or []
            parts = [summary.strip()] if summary else []
            for art in artifacts[:3]:
                name = getattr(art, "name", "artifact")
                content = str(getattr(art, "content", "") or "")
                if content.strip():
                    parts.append(f"[{name}]\n{content[:1500]}")
            return "\n\n".join(p for p in parts if p)[:6000]
        except Exception:  # noqa: BLE001
            return ""


memory_client = MemoryClient()
