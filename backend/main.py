"""
backend/main.py
===============
FastAPI application entry point.

Start the server:
    uvicorn backend.main:app --reload --port 8000
or:
    python -m backend.main
"""

from __future__ import annotations

import os
import sys
from dotenv import load_dotenv
load_dotenv()

# Ensure the project root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import ai, export, files, markdown

app = FastAPI(
    title="Markdown Reader API",
    description="Local Python backend for Markdown Reader desktop application.",
    version="2.0.0",
)

# Allow the Next.js dev server and Tauri webview to communicate with us.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://localhost:3001",
        "tauri://localhost",  # Tauri webview
        "https://tauri.localhost",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(files.router, prefix="/api/files", tags=["files"])
app.include_router(markdown.router, prefix="/api/markdown", tags=["markdown"])
app.include_router(ai.router, prefix="/api/ai", tags=["ai"])
app.include_router(export.router, prefix="/api/export", tags=["export"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def _find_free_port() -> int:
    """Ask the OS for an available TCP port on 127.0.0.1."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def main() -> None:
    """Entry point used by pyproject.toml [project.scripts] and the Tauri sidecar.

    Prints ``BACKEND_PORT=<port>`` to stdout before starting, so the Tauri
    host process can read the dynamically assigned port and pass it to the
    web-view — no hard-coded port number anywhere.
    """
    port = _find_free_port()
    # Flush immediately so the Tauri stdout reader sees it without delay.
    print(f"BACKEND_PORT={port}", flush=True)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()


def main():
    """Entry point for the 'markdown-reader-backend' script."""
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
