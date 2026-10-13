"""
Hybrid knowledge-graph builder for a project's codebase.

Two layers, GitNexus-style:
  1. STATIC (deterministic, regex/line-based): a rich code graph —
     folder / file / class / method / function / external-package nodes, with
     CONTAINS, IMPORTS, INHERITS and (heuristic) CALLS edges.
  2. SEMANTIC (LLM): high-level entities (services, components, data models,
     concepts) and their relationships, from a compact project digest.

Best-effort throughout: the semantic layer degrades gracefully without an LLM.
"""
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

import structlog

from app.core.config import settings
from app.core.llm_client import llm_client

logger = structlog.get_logger()

IGNORED_SEGMENTS = {".git", "node_modules", "__pycache__", ".next", "dist", "build", ".venv", "venv", ".idea", ".vscode"}
SOURCE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rb", ".php", ".cs", ".rs", ".vue", ".svelte"}
DOC_EXTS = {".md", ".json", ".yml", ".yaml", ".toml"}
JS_EXTS = {".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}

MAX_FILES = 400
MAX_FILE_BYTES = 200_000
# Names that would create call-edge noise if linked.
_CALL_STOP = {
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
    "range", "enumerate", "zip", "map", "filter", "open", "super", "isinstance",
    "type", "format", "join", "append", "get", "set", "log", "error", "warn", "info",
    "require", "console", "return", "if", "for", "while", "function", "class",
}


def _iter_source_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        if any(seg in IGNORED_SEGMENTS for seg in p.parts):
            continue
        if p.suffix.lower() in SOURCE_EXTS or p.suffix.lower() in DOC_EXTS:
            files.append(p)
        if len(files) >= MAX_FILES:
            break
    return files


def _read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_BYTES]
    except Exception:  # noqa: BLE001
        return ""


def _resolve_relative_js(importer: Path, spec: str, root: Path, by_rel: Dict[str, str]) -> str | None:
    if not spec.startswith("."):
        return None
    target = (importer.parent / spec).resolve()
    candidates = [target]
    for ext in (".ts", ".tsx", ".js", ".jsx", ".vue"):
        candidates.append(target.with_suffix(ext))
        candidates.append(target / f"index{ext}")
    for cand in candidates:
        try:
            rel = cand.relative_to(root).as_posix()
        except ValueError:
            continue
        if rel in by_rel:
            return rel
    return None


def _resolve_python(spec: str, by_rel: Dict[str, str]) -> str | None:
    mod = spec.lstrip(".")
    parts = mod.split(".")
    for depth in range(len(parts), 0, -1):
        base = "/".join(parts[:depth])
        for cand in (f"{base}.py", f"{base}/__init__.py"):
            if cand in by_rel:
                return cand
    return None


# ── Static layer ────────────────────────────────────────────────────────────
def _static_graph(root: Path, files: List[Path]) -> Tuple[List[Dict], List[Dict]]:
    nodes: Dict[str, Dict] = {}
    edges: List[Dict] = []
    rels = [f.relative_to(root).as_posix() for f in files]
    by_rel = {r: r for r in rels}

    def add_node(key: str, label: str, ntype: str, meta: dict | None = None) -> None:
        if key not in nodes:
            nodes[key] = {"key": key, "label": label, "type": ntype, "meta": meta or {}}

    def add_edge(s: str, t: str, rel: str) -> None:
        edges.append({"source": s, "target": t, "relation": rel})

    # 1) folder + file structure (CONTAINS)
    for r in rels:
        parts = r.split("/")
        parent = None
        for i in range(len(parts) - 1):
            fkey = "dir:" + "/".join(parts[: i + 1])
            add_node(fkey, parts[i], "folder", {"path": "/".join(parts[: i + 1])})
            if parent:
                add_edge(parent, fkey, "contains")
            parent = fkey
        add_node(r, parts[-1], "file", {"path": r, "ext": Path(r).suffix.lower()})
        if parent:
            add_edge(parent, r, "contains")

    class_index: Dict[str, str] = {}       # class name -> node key
    callable_index: Dict[str, str] = {}    # bare callable name -> node key
    inherits: List[Tuple[str, str]] = []   # (child class key, base name)
    calls: List[Tuple[str, str]] = []      # (caller node key, callee name)

    for f in files:
        rel = f.relative_to(root).as_posix()
        ext = f.suffix.lower()
        if ext in DOC_EXTS:
            continue
        text = _read(f)
        if ext == ".py":
            _parse_python(rel, text, by_rel, add_node, add_edge, class_index, callable_index, inherits, calls)
        elif ext in JS_EXTS:
            _parse_js(rel, f, text, root, by_rel, add_node, add_edge, class_index, callable_index, inherits, calls)

    # 2) resolve INHERITS (to a known class node, else an external node)
    for child_key, base in inherits:
        if base in class_index:
            add_edge(child_key, class_index[base], "inherits")
        else:
            ek = f"ext:{base}"
            add_node(ek, base, "external", {"external": True})
            add_edge(child_key, ek, "inherits")

    # 3) resolve CALLS (only unambiguous, non-trivial names)
    seen_calls = set()
    for caller_key, callee in calls:
        if callee in _CALL_STOP or callee not in callable_index:
            continue
        target = callable_index[callee]
        if target == caller_key:
            continue
        sig = (caller_key, target)
        if sig in seen_calls:
            continue
        seen_calls.add(sig)
        add_edge(caller_key, target, "calls")

    return list(nodes.values()), edges


def _parse_python(rel, text, by_rel, add_node, add_edge, class_index, callable_index, inherits, calls) -> None:
    lines = text.split("\n")
    current_class: Tuple[str, int, str] | None = None
    current_callable: str | None = None
    current_callable_indent = -1
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()

        m = re.match(r"(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))", stripped)
        if m:
            spec = m.group(1) or m.group(2) or ""
            tgt = _resolve_python(spec, by_rel)
            if tgt and tgt != rel:
                add_edge(rel, tgt, "imports")
            elif spec and not spec.startswith("."):
                pkg = spec.split(".")[0]
                add_node(f"ext:{pkg}", pkg, "external", {"external": True})
                add_edge(rel, f"ext:{pkg}", "imports")
            continue

        cm = re.match(r"class\s+(\w+)\s*(?:\(([^)]*)\))?", stripped)
        if cm and indent == 0:
            cname = cm.group(1)
            ckey = f"{rel}::{cname}"
            add_node(ckey, cname, "class", {"file": rel})
            add_edge(rel, ckey, "contains")
            class_index.setdefault(cname, ckey)
            for base in re.findall(r"\w+", cm.group(2) or ""):
                if base not in ("object", "ABC"):
                    inherits.append((ckey, base))
            current_class = (ckey, indent, cname)
            current_callable, current_callable_indent = None, -1
            continue

        dm = re.match(r"(?:async\s+)?def\s+(\w+)", stripped)
        if dm:
            fname = dm.group(1)
            if current_class and indent > current_class[1]:
                key = f"{current_class[0]}.{fname}"
                add_node(key, f"{fname}()", "method", {"file": rel, "class": current_class[2]})
                add_edge(current_class[0], key, "contains")
            else:
                key = f"{rel}::{fname}()"
                add_node(key, f"{fname}()", "function", {"file": rel})
                add_edge(rel, key, "contains")
                current_class = None
            callable_index.setdefault(fname, key)
            current_callable, current_callable_indent = key, indent
            continue

        # end of class scope on a dedent to column 0
        if indent == 0 and current_class:
            current_class = None

        # attribute call tokens to the enclosing callable
        if current_callable and indent > current_callable_indent:
            for callee in re.findall(r"(?:self\.)?(\w+)\s*\(", stripped):
                calls.append((current_callable, callee))
        elif current_callable and indent <= current_callable_indent:
            current_callable, current_callable_indent = None, -1


_JS_CLASS = re.compile(r"\bclass\s+([A-Z]\w+)(?:\s+extends\s+([A-Za-z_$][\w$.]*))?")
_JS_FUNC = re.compile(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)|(?:export\s+)?const\s+(\w+)\s*=\s*(?:async\s*)?\(")


def _parse_js(rel, f, text, root, by_rel, add_node, add_edge, class_index, callable_index, inherits, calls) -> None:
    # imports (internal + external)
    for m in re.finditer(r"""(?:import\s.*?from\s*|require\(\s*)['"]([^'"]+)['"]""", text):
        spec = m.group(1)
        tgt = _resolve_relative_js(f, spec, root, by_rel)
        if tgt and tgt != rel:
            add_edge(rel, tgt, "imports")
        elif not spec.startswith("."):
            pkg = spec.split("/")[0]
            add_node(f"ext:{pkg}", pkg, "external", {"external": True})
            add_edge(rel, f"ext:{pkg}", "imports")

    for m in _JS_CLASS.finditer(text):
        cname, base = m.group(1), m.group(2)
        ckey = f"{rel}::{cname}"
        add_node(ckey, cname, "class", {"file": rel})
        add_edge(rel, ckey, "contains")
        class_index.setdefault(cname, ckey)
        if base:
            inherits.append((ckey, base.split(".")[-1]))

    for m in _JS_FUNC.finditer(text):
        fname = m.group(1) or m.group(2)
        if not fname:
            continue
        key = f"{rel}::{fname}()"
        add_node(key, f"{fname}()", "function", {"file": rel})
        add_edge(rel, key, "contains")
        callable_index.setdefault(fname, key)

    # coarse calls: file -> callee (JS scoping is hard to do with regex)
    for callee in set(re.findall(r"\b(\w+)\s*\(", text)):
        calls.append((rel, callee))


# ── Semantic layer (LLM) ────────────────────────────────────────────────────
def _project_digest(root: Path, files: List[Path]) -> str:
    tree = "\n".join(f.relative_to(root).as_posix() for f in files[:200])
    priority = ("readme", "package.json", "main", "app", "index", "requirements", "pom.xml", "go.mod")
    picked = [f for f in files if any(k in f.name.lower() for k in priority)][:6]
    snippets = []
    for f in picked:
        rel = f.relative_to(root).as_posix()
        snippets.append(f"--- {rel} ---\n{_read(f)[:1500]}")
    return f"FILE TREE:\n{tree}\n\nKEY FILES:\n" + "\n\n".join(snippets)


async def _semantic_graph(root: Path, files: List[Path]) -> Tuple[List[Dict], List[Dict]]:
    digest = _project_digest(root, files)
    system = (
        "You are a software architect. Extract a concise KNOWLEDGE GRAPH of the project's "
        "high-level architecture from the digest. Focus on meaningful entities and how they "
        "relate — NOT every file."
    )
    user = f"""{digest[:8000]}

Return ONLY valid JSON (no markdown fences) in this exact shape:
{{
  "nodes": [{{"key":"short-slug","label":"Human Name","type":"service|component|datamodel|concept|external"}}],
  "edges": [{{"source":"slug","target":"slug","relation":"depends_on|uses|relates_to"}}]
}}
Rules: 8-20 nodes max. keys are short lowercase slugs. Every edge's source/target MUST be a node key above."""
    try:
        raw = await llm_client.complete(system_prompt=system, user_prompt=user, temperature=0.2)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Semantic KG layer failed", error=str(exc))
        return [], []

    payload = _extract_json(raw)
    if not payload:
        return [], []
    nodes, edges = [], []
    valid_types = {"service", "component", "datamodel", "concept", "external"}
    keys = set()
    for n in payload.get("nodes", []) or []:
        if not isinstance(n, dict):
            continue
        key = str(n.get("key") or "").strip()
        if not key:
            continue
        skey = f"concept:{key}"
        ntype = str(n.get("type") or "concept")
        if ntype not in valid_types:
            ntype = "concept"
        keys.add(key)
        nodes.append({"key": skey, "label": str(n.get("label") or key), "type": ntype, "meta": {"semantic": True}})
    for e in payload.get("edges", []) or []:
        if not isinstance(e, dict):
            continue
        s, t = str(e.get("source") or ""), str(e.get("target") or "")
        if s in keys and t in keys and s != t:
            edges.append({"source": f"concept:{s}", "target": f"concept:{t}", "relation": str(e.get("relation") or "relates_to")})
    return nodes, edges


def _extract_json(text: str) -> Dict[str, Any] | None:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    match = re.search(r"\{.*\}", t, re.DOTALL)
    for cand in (t, match.group(0) if match else ""):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:  # noqa: BLE001
            continue
    return None


# ── Public API ──────────────────────────────────────────────────────────────
async def build_knowledge_graph(project_id: str, with_semantic: bool = True) -> Dict[str, Any]:
    root = (Path(settings.WORKSPACE_ROOT) / project_id).resolve()
    if not root.exists():
        return {"ok": False, "error": "project workspace is empty — import code first"}
    files = _iter_source_files(root)
    if not files:
        return {"ok": False, "error": "no source files found in the project"}

    nodes, edges = _static_graph(root, files)

    if with_semantic:
        s_nodes, s_edges = await _semantic_graph(root, files)
        nodes.extend(s_nodes)
        edges.extend(s_edges)

    node_map = {n["key"]: n for n in nodes}
    node_keys = set(node_map)
    seen_e = set()
    uniq_edges = []
    for e in edges:
        if e["source"] not in node_keys or e["target"] not in node_keys:
            continue
        sig = (e["source"], e["target"], e["relation"])
        if sig in seen_e:
            continue
        seen_e.add(sig)
        uniq_edges.append(e)

    by_type: Dict[str, int] = {}
    for n in node_map.values():
        by_type[n["type"]] = by_type.get(n["type"], 0) + 1

    return {
        "ok": True,
        "nodes": list(node_map.values()),
        "edges": uniq_edges,
        "stats": {"nodes": len(node_map), "edges": len(uniq_edges), "by_type": by_type},
    }
