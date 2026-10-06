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
import threading
import time

from dotenv import load_dotenv

load_dotenv()

# Ensure the project root is importable
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import ai, citations, export, files, knowledge, markdown

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
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
        "tauri://localhost",  # Tauri webview
        "http://tauri.localhost",
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
app.include_router(citations.router, prefix="/api/citations", tags=["citations"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["knowledge"])


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


def _find_free_port() -> int:
    """Ask the OS for an available TCP port on 127.0.0.1."""
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# STILL_ACTIVE is what GetExitCodeProcess reports for a process that has not
# exited; PROCESS_QUERY_LIMITED_INFORMATION is the narrowest right that still
# answers the same question.
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_ERROR_ACCESS_DENIED = 5


def _parent_is_running(pid: int) -> bool:
    """Whether ``pid`` still names a live process.

    ``os.kill(pid, 0)`` asks that without touching the process on POSIX, but it
    is not a probe on Windows: every signal outside the two console events is
    handed to ``TerminateProcess``, so a 0 there kills the very process being
    inspected (https://docs.python.org/3/library/os.html#os.kill). Read the exit
    code instead.
    """
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            # The pid is taken, just not by us.
            return True
        return True

    import ctypes

    kernel32 = ctypes.WinDLL("kernel32")
    # Declared rather than left to ctypes' defaults: a handle is pointer-sized,
    # so the default c_int return type would truncate it on 64-bit Windows.
    kernel32.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.GetExitCodeProcess.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint32),
    )
    kernel32.GetExitCodeProcess.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int
    kernel32.GetLastError.argtypes = ()
    kernel32.GetLastError.restype = ctypes.c_uint32

    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # An access-denied error still means the pid exists.  Conservatively
        # leave the sidecar running rather than orphan it while its host lives.
        return kernel32.GetLastError() == _ERROR_ACCESS_DENIED
    try:
        exit_code = ctypes.c_uint32()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        # A handle can outlive the process it names, so opening one is not
        # proof of life; STILL_ACTIVE is.
        return exit_code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def _start_parent_watchdog() -> None:
    """Exit the sidecar if the Tauri host process is gone."""
    parent_pid = os.environ.get("MARKDOWN_READER_PARENT_PID")
    if not parent_pid:
        return

    try:
        pid = int(parent_pid)
    except ValueError:
        return

    def watch_parent() -> None:
        while True:
            time.sleep(2)
            if not _parent_is_running(pid):
                os._exit(0)

    threading.Thread(target=watch_parent, daemon=True).start()


def main() -> None:
    """Entry point used by pyproject.toml [project.scripts] and the Tauri sidecar.

    Prints ``BACKEND_PORT=<port>`` to stdout before starting, so the Tauri
    host process can read the dynamically assigned port and pass it to the
    web-view — no hard-coded port number anywhere.
    """
    _start_parent_watchdog()
    port = _find_free_port()
    # Flush immediately so the Tauri stdout reader sees it without delay.
    print(f"BACKEND_PORT={port}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=port, reload=False)


if __name__ == "__main__":
    main()
