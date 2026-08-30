"""
backend/routers/citations.py
=============================
Academic citation support: load a BibTeX (.bib) library and search it
from the editor.
"""

from __future__ import annotations

import os
import sys

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

router = APIRouter()


def _logic():
    """Import citation logic only when a citations endpoint is used."""
    from backend import citation_logic

    return citation_logic


# ── Models ────────────────────────────────────────────────────────────────────


class LoadLibraryPayload(BaseModel):
    path: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/load")
def load_library(payload: LoadLibraryPayload):
    """Parse a .bib file and set it as the active citation library."""
    logic = _logic()
    try:
        entries = logic.load_citation_library(payload.path)
    except logic.CitationLibraryError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"path": os.path.abspath(payload.path), "count": len(entries), "entries": entries}


@router.get("/list")
def list_library():
    """Return all entries in the currently active library."""
    logic = _logic()
    entries = logic.get_active_library_entries()
    return {"path": logic.get_persisted_library_path(), "entries": entries}


@router.get("/search")
def search_library(q: str = Query("", description="Search text")):
    """Search the active library by key, author, title, or year."""
    logic = _logic()
    return {"entries": logic.search_citations(q)}
