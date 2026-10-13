"""
Nexus — Skills & Templates.

A "skill" is a reusable instruction block (a capability or a prompt template)
that can be attached to agents. When an agent runs, the instructions of its
assigned skills are injected into its system prompt, so skills actually change
agent behaviour — they are not just metadata.

Assignment is stored on the agent's config.skills = [slug, ...] (edited via
PATCH /agents/{id}). This endpoint owns the skill catalog CRUD.
"""
import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.database import get_session

router = APIRouter()

_TABLE_READY = False

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS skills (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  slug          VARCHAR(255) UNIQUE NOT NULL,
  name          VARCHAR(255) NOT NULL,
  description   TEXT,
  category      VARCHAR(100) NOT NULL DEFAULT 'general',
  kind          VARCHAR(50) NOT NULL DEFAULT 'skill',
  instructions  TEXT NOT NULL,
  tags          TEXT[] DEFAULT ARRAY[]::TEXT[],
  is_active     BOOLEAN NOT NULL DEFAULT TRUE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""

SEED_SKILLS = [
    {
        "slug": "clean-code",
        "name": "Clean Code Standards",
        "description": "Enforce readable, well-structured, documented code.",
        "category": "engineering",
        "kind": "skill",
        "instructions": (
            "Follow clean code principles: small focused functions, meaningful names, no dead code, "
            "handle errors and edge cases explicitly, and add concise comments only where intent is non-obvious."
        ),
        "tags": ["quality", "engineering"],
    },
    {
        "slug": "owasp-security",
        "name": "OWASP Security Review",
        "description": "Check work against the OWASP Top 10.",
        "category": "security",
        "kind": "skill",
        "instructions": (
            "Actively check for the OWASP Top 10: injection, broken auth, XSS, insecure deserialization, "
            "sensitive data exposure, and misconfiguration. Never output secrets. Prefer parameterized queries "
            "and safe DOM APIs."
        ),
        "tags": ["security"],
    },
    {
        "slug": "accessible-ui",
        "name": "Accessible UI",
        "description": "Produce WCAG-friendly, responsive interfaces.",
        "category": "frontend",
        "kind": "skill",
        "instructions": (
            "Build accessible UI: semantic HTML, labelled controls, keyboard support, sufficient color contrast, "
            "focus states, and responsive layouts that work on mobile and desktop."
        ),
        "tags": ["frontend", "ux"],
    },
    {
        "slug": "landing-page-template",
        "name": "Landing Page Template",
        "description": "A reusable brief for building a marketing landing page.",
        "category": "frontend",
        "kind": "template",
        "instructions": (
            "Structure the page as: sticky nav, hero with headline + subhead + CTA, 3-4 feature cards, "
            "social proof section, pricing or CTA band, and footer. Use a cohesive color system and modern spacing."
        ),
        "tags": ["template", "marketing"],
    },
]


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug or "skill"


async def ensure_skills_table() -> None:
    """Create the skills table on demand (existing DBs were initialised before this feature)."""
    global _TABLE_READY
    if _TABLE_READY:
        return
    async with get_session() as session:
        await session.execute(text(CREATE_TABLE_SQL))
        # seed examples only if the table is empty
        count = (await session.execute(text("SELECT COUNT(*) FROM skills"))).scalar() or 0
        if count == 0:
            for s in SEED_SKILLS:
                await session.execute(
                    text(
                        "INSERT INTO skills (slug, name, description, category, kind, instructions, tags) "
                        "VALUES (:slug, :name, :description, :category, :kind, :instructions, :tags) "
                        "ON CONFLICT (slug) DO NOTHING"
                    ),
                    {**s, "tags": s["tags"]},
                )
        await session.commit()
    _TABLE_READY = True


class SkillUpsert(BaseModel):
    name: str
    description: Optional[str] = ""
    category: Optional[str] = "general"
    kind: Optional[str] = "skill"
    instructions: str
    tags: Optional[List[str]] = None
    is_active: Optional[bool] = True


def _row(row: Any) -> Dict[str, Any]:
    return dict(row)


@router.get("/")
async def list_skills():
    await ensure_skills_table()
    async with get_session() as session:
        result = await session.execute(text(
            "SELECT id, slug, name, description, category, kind, instructions, tags, is_active, "
            "created_at, updated_at FROM skills ORDER BY category, name"
        ))
        rows = result.mappings().all()
        return {"data": [_row(r) for r in rows], "total": len(rows)}


@router.post("/")
async def create_skill(body: SkillUpsert):
    await ensure_skills_table()
    slug = _slugify(body.name)
    async with get_session() as session:
        # ensure unique slug
        exists = (await session.execute(text("SELECT 1 FROM skills WHERE slug = :s"), {"s": slug})).first()
        if exists:
            slug = f"{slug}-{(await session.execute(text('SELECT COUNT(*) FROM skills'))).scalar()}"
        result = await session.execute(
            text(
                "INSERT INTO skills (slug, name, description, category, kind, instructions, tags, is_active) "
                "VALUES (:slug, :name, :description, :category, :kind, :instructions, :tags, :is_active) "
                "RETURNING *"
            ),
            {
                "slug": slug, "name": body.name, "description": body.description or "",
                "category": body.category or "general", "kind": body.kind or "skill",
                "instructions": body.instructions, "tags": body.tags or [],
                "is_active": body.is_active if body.is_active is not None else True,
            },
        )
        await session.commit()
        return _row(result.mappings().first())


@router.patch("/{skill_id}")
async def update_skill(skill_id: str, body: SkillUpsert):
    await ensure_skills_table()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(400, "No fields to update")
    set_clauses = ", ".join(f"{k} = :{k}" for k in updates)
    params = {**updates, "id": skill_id}
    async with get_session() as session:
        result = await session.execute(
            text(f"UPDATE skills SET {set_clauses}, updated_at = NOW() WHERE id = :id RETURNING *"),
            params,
        )
        await session.commit()
        row = result.mappings().first()
        if not row:
            raise HTTPException(404, f"Skill '{skill_id}' not found")
        return _row(row)


@router.delete("/{skill_id}")
async def delete_skill(skill_id: str):
    await ensure_skills_table()
    async with get_session() as session:
        result = await session.execute(text("DELETE FROM skills WHERE id = :id RETURNING slug"), {"id": skill_id})
        await session.commit()
        if not result.first():
            raise HTTPException(404, f"Skill '{skill_id}' not found")
        return {"deleted": True}
