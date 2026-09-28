"""
backend/routers/knowledge.py
=============================
Directory-level context / local RAG endpoints for personal notes and workspaces.
"""

from __future__ import annotations

import os
import sys
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

router = APIRouter()


def _logic():
    from backend import knowledge_logic

    return knowledge_logic


# ── Models ────────────────────────────────────────────────────────────────────


class IndexKnowledgePayload(BaseModel):
    path: str
    force: bool = False


class QueryKnowledgePayload(BaseModel):
    query: str
    top_k: int = 5


class KnowledgeTogglePayload(BaseModel):
    enabled: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/status")
def get_status() -> dict[str, Any]:
    """Return status and metadata for the configured knowledge base directory."""
    return _logic().get_knowledge_base_status()


@router.post("/index")
def index_directory(payload: IndexKnowledgePayload) -> dict[str, Any]:
    """Index or re-index notes in the specified local directory."""
    logic = _logic()
    try:
        stats = logic.index_knowledge_base(payload.path, force=payload.force)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {exc}")
    return stats


@router.post("/query")
def query_knowledge(payload: QueryKnowledgePayload) -> dict[str, Any]:
    """Search for notes and excerpts relevant to the given query."""
    logic = _logic()
    results = logic.query_knowledge_base(payload.query, top_k=payload.top_k)
    return {
        "query": payload.query,
        "count": len(results),
        "results": results,
    }


@router.get("/notes")
def list_notes(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    """Return a list of indexed notes in the knowledge base."""
    logic = _logic()
    notes = logic.list_indexed_notes(limit=limit)
    return {"count": len(notes), "notes": notes}


@router.post("/toggle")
def toggle_knowledge(payload: KnowledgeTogglePayload) -> dict[str, Any]:
    """Enable or disable directory context."""
    logic = _logic()
    logic.set_knowledge_base_enabled(payload.enabled)
    return {"enabled": payload.enabled}


@router.delete("/index")
def clear_index() -> dict[str, Any]:
    """Clear all indexed data from the knowledge base."""
    logic = _logic()
    logic.clear_knowledge_base()
    return {"cleared": True}
