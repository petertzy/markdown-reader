"""
recent_files.py
===============
Persistent "Recent Files" submenu for the Markdown Reader application.

Integration points (in app.py):
  1. Import:
         from recent_files import RecentFilesManager

  2. After creating the app window and settings infrastructure, instantiate:
         self.recent_files = RecentFilesManager(settings_path=self._settings_path())

     where self._settings_path() returns the same path already used for AI
     provider settings (platform-appropriate JSON file).

  3. Build the File menu entry:
         self.recent_files.build_menu(file_menu, open_callback=self.open_file)

     Pass the *same* callable you use for "File → Open File" so that
     clicking a recent entry behaves identically.

  4. Every time a file is successfully opened by any mechanism
     (menu, drag-and-drop, double-click), call:
         self.recent_files.push(filepath)

  5. If you rebuild the File menu dynamically, call
         self.recent_files.rebuild_menu()
     to refresh the submenu entries.

Dependencies: stdlib only (json, os, pathlib, tempfile, tkinter)
"""

from __future__ import annotations

import json
import os
import pathlib
import tempfile
import tkinter as tk
from typing import Callable


# Maximum number of recent paths to remember.
_MAX_ENTRIES = 10

# JSON key used inside the existing settings file.
_SETTINGS_KEY = "recent_files"

# Maximum display length (characters) for a path label in the menu.
# Paths longer than this are truncated with a middle ellipsis.
_MAX_DISPLAY_LEN = 60


def _middle_ellipsis(path: str, max_len: int = _MAX_DISPLAY_LEN) -> str:
    """
    Shorten *path* to at most *max_len* characters using a middle ellipsis.

    Example: '/very/long/path/to/some/file.md'  →  '/very/long/…/file.md'
    """
    if len(path) <= max_len:
        return path
    half = (max_len - 1) // 2
    return path[:half] + "…" + path[-(max_len - half - 1):]


def _safe_write_json(filepath: str, data: dict) -> None:
    """
    Write *data* as JSON to *filepath* using an atomic rename pattern.

    Writes to a sibling temp file first, then renames it over the target.
    This prevents corruption if the process is killed mid-write.
    """
    directory = os.path.dirname(filepath) or "."
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        # os.replace is atomic on POSIX; on Windows it is also atomic since
        # Python 3.3 (uses MoveFileExW under the hood).
        os.replace(tmp_path, filepath)
    except Exception:
        # Best-effort cleanup of the temp file if something went wrong.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class RecentFilesManager:
    """
    Manages a persistent MRU (most-recently-used) file list stored as a key
    inside the application's existing settings JSON file.

    The list is ordered most-recent-first.  Entries pointing to files that no
    longer exist on disk are silently pruned on every load.

    Parameters
    ----------
    settings_path:
        Absolute path to the application's settings JSON file.  The file is
        created if it does not yet exist.
    max_entries:
        Maximum number of paths to remember (default 10).
    """

    def __init__(
        self,
        settings_path: str,
        max_entries: int = _MAX_ENTRIES,
    ) -> None:
        self._settings_path = settings_path
        self._max_entries = max_entries
        self._entries: list[str] = []
        self._menu: tk.Menu | None = None
        self._open_callback: Callable[[str], None] | None = None

        self._load()

    # ── public API ───────────────────────────────────────────────────────────

    def push(self, filepath: str) -> None:
        """
        Record *filepath* as the most-recently-opened file.

        Normalises the path, deduplicates, prepends, trims to max_entries,
        and persists to disk.
        """
        normalised = os.path.normpath(os.path.abspath(filepath))
        # Remove any existing occurrence so the path moves to the top.
        self._entries = [e for e in self._entries if e != normalised]
        self._entries.insert(0, normalised)
        self._entries = self._entries[: self._max_entries]
        self._save()
        if self._menu is not None:
            self._populate_menu()

    def clear(self) -> None:
        """Remove all entries from the list and persist."""
        self._entries = []
        self._save()
        if self._menu is not None:
            self._populate_menu()

    def build_menu(
        self,
        parent_menu: tk.Menu,
        open_callback: Callable[[str], None],
        label: str = "Recent Files",
    ) -> tk.Menu:
        """
        Create and attach a "Recent Files" cascade submenu to *parent_menu*.

        Parameters
        ----------
        parent_menu:
            The File menu (or any tk.Menu) to which the submenu is added.
        open_callback:
            Called with a single argument — the absolute file path — when the
            user clicks a recent-file entry.  Should be the same function used
            for "File → Open File".
        label:
            Menu label for the cascade item (default "Recent Files").

        Returns
        -------
        The tk.Menu instance that was created (useful if you need to store a
        reference for later rebuilding).
        """
        self._open_callback = open_callback
        self._menu = tk.Menu(parent_menu, tearoff=False)
        parent_menu.add_cascade(label=label, menu=self._menu)
        self._populate_menu()
        return self._menu

    def rebuild_menu(self) -> None:
        """
        Refresh the submenu entries from the current in-memory list.

        Call this whenever you need to force a visual update outside of
        ``push()`` or ``clear()``.
        """
        if self._menu is not None:
            self._populate_menu()

    @property
    def entries(self) -> list[str]:
        """Read-only snapshot of the current recent-file paths (most-recent first)."""
        return list(self._entries)

    # ── private helpers ──────────────────────────────────────────────────────

    def _load(self) -> None:
        """
        Read the recent-files list from the settings JSON file.

        • If the file does not exist yet, initialises an empty list.
        • If the JSON is malformed, falls back to an empty list (never crashes).
        • Silently drops paths that no longer exist on disk.
        """
        if not os.path.isfile(self._settings_path):
            self._entries = []
            return
        try:
            with open(self._settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw: list = data.get(_SETTINGS_KEY, [])
            if not isinstance(raw, list):
                raw = []
            # Normalise and prune missing files.
            self._entries = [
                os.path.normpath(p)
                for p in raw
                if isinstance(p, str) and os.path.isfile(p)
            ][: self._max_entries]
        except (json.JSONDecodeError, OSError):
            self._entries = []

    def _save(self) -> None:
        """
        Merge the current recent-files list into the settings JSON file.

        Reads the existing settings first so that other keys (API keys, theme
        preferences, etc.) are preserved.  Uses an atomic write to avoid
        corruption.
        """
        # Read existing settings (if any).
        data: dict = {}
        if os.path.isfile(self._settings_path):
            try:
                with open(self._settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                data = {}

        # Ensure the parent directory exists.
        parent = os.path.dirname(self._settings_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        data[_SETTINGS_KEY] = self._entries
        _safe_write_json(self._settings_path, data)

    def _populate_menu(self) -> None:
        """
        Rebuild all entries inside the submenu from the current list.

        Called automatically after every push/clear and after build_menu().
        """
        menu = self._menu
        menu.delete(0, "end")

        if not self._entries:
            # Show a disabled placeholder so the submenu is never blank.
            menu.add_command(label="(no recent files)", state="disabled")
        else:
            for path in self._entries:
                display = _middle_ellipsis(path)
                exists = os.path.isfile(path)
                label = display if exists else f"{display}  [not found]"
                state = "normal" if exists else "disabled"
                # Capture `path` in the default-argument closure.
                menu.add_command(
                    label=label,
                    state=state,
                    command=lambda p=path: self._on_click(p),
                )
            menu.add_separator()
            menu.add_command(label="Clear Recent Files", command=self.clear)

    def _on_click(self, path: str) -> None:
        """Handle a click on a recent-file menu entry."""
        if not os.path.isfile(path):
            # File disappeared between menu open and click.
            # Remove it and refresh — don't crash.
            self._entries = [e for e in self._entries if e != path]
            self._save()
            self._populate_menu()
            return
        if self._open_callback is not None:
            self._open_callback(path)