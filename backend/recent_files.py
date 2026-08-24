from __future__ import annotations

import json
import os
import tempfile

_MAX_ENTRIES = 10
_SETTINGS_KEY = "recent_files"
_MAX_DISPLAY_LEN = 60


def _middle_ellipsis(path: str, max_len: int = _MAX_DISPLAY_LEN) -> str:
    if len(path) <= max_len:
        return path
    half = (max_len - 1) // 2
    return path[:half] + "…" + path[-(max_len - half - 1) :]


def _safe_write_json(filepath: str, data: dict) -> None:
    directory = os.path.dirname(filepath) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(data, file_obj, indent=2, ensure_ascii=False)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class RecentFilesManager:
    def __init__(self, settings_path: str, max_entries: int = _MAX_ENTRIES) -> None:
        self._settings_path = settings_path
        self._max_entries = max_entries
        self._entries: list[str] = []
        self._load()

    @property
    def entries(self) -> list[str]:
        return list(self._entries)

    def push(self, filepath: str) -> None:
        normalized = os.path.normpath(os.path.abspath(filepath))
        self._entries = [entry for entry in self._entries if entry != normalized]
        self._entries.insert(0, normalized)
        self._entries = self._entries[: self._max_entries]
        self._save()

    def clear(self) -> None:
        self._entries = []
        self._save()

    def _load(self) -> None:
        if not os.path.isfile(self._settings_path):
            self._entries = []
            return
        try:
            with open(self._settings_path, encoding="utf-8") as file_obj:
                data = json.load(file_obj)
            raw = data.get(_SETTINGS_KEY, [])
            if not isinstance(raw, list):
                raw = []
            self._entries = [
                os.path.normpath(path)
                for path in raw
                if isinstance(path, str) and os.path.isfile(path)
            ][: self._max_entries]
        except (json.JSONDecodeError, OSError):
            self._entries = []

    def _save(self) -> None:
        data: dict = {}
        if os.path.isfile(self._settings_path):
            try:
                with open(self._settings_path, encoding="utf-8") as file_obj:
                    data = json.load(file_obj)
            except (json.JSONDecodeError, OSError):
                data = {}
        data[_SETTINGS_KEY] = self._entries
        _safe_write_json(self._settings_path, data)
