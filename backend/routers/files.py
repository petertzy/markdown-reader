"""
backend/routers/files.py
========================
File system CRUD endpoints + recent-files management.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from markdown_reader.logic import APP_SETTINGS_FILE_PATH
from markdown_reader.recent_files import RecentFilesManager

router = APIRouter()

# Singleton recent-files manager (shared across requests)
_recent: RecentFilesManager | None = None


def _get_recent() -> RecentFilesManager:
    global _recent
    if _recent is None:
        _recent = RecentFilesManager(str(APP_SETTINGS_FILE_PATH))
    return _recent


# ── Models ────────────────────────────────────────────────────────────────────


class WritePayload(BaseModel):
    path: str
    content: str


class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    extension: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/read")
def read_file(path: str = Query(..., description="Absolute path to the file")):
    """Read a file and return its content."""
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            content = f.read()
        return {"path": path, "content": content}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/write")
def write_file(payload: WritePayload):
    """Write (or overwrite) a file with the provided content."""
    path = payload.path
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload.content)
        return {"path": path, "written": True}
    except OSError as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/list")
def list_files(
    path: str = Query(..., description="Directory to list"),
    extensions: str | None = Query(
        None,
        description="Comma-separated list of file extensions to include (e.g. md,txt)",
    ),
):
    """List entries in a directory (non-recursive, sorted: dirs first)."""
    if not os.path.isdir(path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    allowed_exts: set[str] | None = None
    if extensions:
        allowed_exts = {e.strip().lower().lstrip(".") for e in extensions.split(",")}

    entries: list[dict] = []
    try:
        with os.scandir(path) as it:
            for entry in sorted(it, key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith("."):
                    continue
                is_dir = entry.is_dir()
                ext = Path(entry.name).suffix.lstrip(".").lower()
                if not is_dir and allowed_exts and ext not in allowed_exts:
                    continue
                entries.append(
                    {
                        "name": entry.name,
                        "path": entry.path,
                        "is_dir": is_dir,
                        "extension": ext,
                    }
                )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {"path": path, "entries": entries}


@router.get("/recent")
def get_recent_files():
    """Return the most-recently-opened file paths."""
    return {"entries": _get_recent().entries}


@router.post("/recent")
def add_recent_file(path: str = Query(...)):
    """Record a file as most-recently-opened."""
    _get_recent().push(path)
    return {"entries": _get_recent().entries}


@router.delete("/recent")
def clear_recent_files():
    """Clear all recent-file entries."""
    _get_recent().clear()
    return {"entries": []}
