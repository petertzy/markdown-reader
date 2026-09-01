from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

CITATION_MAX_RESULTS = 50


def _get_settings_file_path() -> Path:
    if sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support" / "MarkdownReader"
    elif sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA", "").strip()
        base_dir = (
            Path(appdata) / "MarkdownReader"
            if appdata
            else Path.home() / "AppData" / "Roaming" / "MarkdownReader"
        )
    else:
        base_dir = Path.home() / ".config" / "markdown-reader"
    return base_dir / "settings.json"


APP_SETTINGS_FILE_PATH = _get_settings_file_path()
_SETTINGS_KEY_LIBRARY_PATH = "citation_library_path"


class CitationLibraryError(RuntimeError):
    """Raised when a .bib file cannot be located or parsed."""


def _load_app_settings() -> dict[str, Any]:
    if not APP_SETTINGS_FILE_PATH.exists():
        return {}
    try:
        with open(APP_SETTINGS_FILE_PATH, encoding="utf-8") as file_obj:
            data = json.load(file_obj)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_app_settings(settings: dict[str, Any]) -> None:
    directory = APP_SETTINGS_FILE_PATH.parent
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            json.dump(settings, file_obj, indent=2, ensure_ascii=False)
        os.replace(tmp_path, APP_SETTINGS_FILE_PATH)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def get_persisted_library_path() -> str:
    """Return the last-loaded .bib path, or '' if none is persisted."""
    path = str(_load_app_settings().get(_SETTINGS_KEY_LIBRARY_PATH, "")).strip()
    return path if path and os.path.isfile(path) else ""


def _same_path(path_a: str, path_b: str) -> bool:
    if not path_a or not path_b:
        return False
    try:
        return os.path.samefile(path_a, path_b)
    except OSError:
        # Fall back to comparing realpaths if one side doesn't exist yet.
        return os.path.realpath(path_a) == os.path.realpath(path_b)


def _set_persisted_library_path(path: str) -> None:
    settings = _load_app_settings()
    settings[_SETTINGS_KEY_LIBRARY_PATH] = path
    _save_app_settings(settings)


def _format_authors(raw_author: str) -> str:
    """Turn BibTeX 'Last, First and Last, First' into 'First Last, First Last'."""
    if not raw_author:
        return ""
    parts = [part.strip() for part in raw_author.split(" and ") if part.strip()]
    formatted = []
    for part in parts:
        if "," in part:
            last, _, first = part.partition(",")
            formatted.append(f"{first.strip()} {last.strip()}".strip())
        else:
            formatted.append(part)
    return ", ".join(formatted)


def _entry_to_dict(entry: dict[str, str]) -> dict[str, str]:
    return {
        "key": entry.get("ID", ""),
        "entry_type": entry.get("ENTRYTYPE", ""),
        "title": entry.get("title", "").strip("{}"),
        "author": _format_authors(entry.get("author", "")),
        "year": entry.get("year", ""),
        "container": entry.get("journal") or entry.get("booktitle") or entry.get(
            "publisher", ""
        ),
    }


def parse_bib_file(path: str) -> list[dict[str, str]]:
    """Parse a .bib file into a list of lightweight citation dicts.

    Raises CitationLibraryError if the file is missing or cannot be parsed.
    """
    if not os.path.isfile(path):
        raise CitationLibraryError(f"BibTeX file not found: {path}")

    try:
        import bibtexparser
    except ImportError as exc:
        raise CitationLibraryError(
            "bibtexparser is required for citation support. "
            "Install it with: pip install bibtexparser"
        ) from exc

    try:
        with open(path, encoding="utf-8", errors="replace") as file_obj:
            database = bibtexparser.load(file_obj)
    except Exception as exc:
        raise CitationLibraryError(f"Could not parse BibTeX file: {exc}") from exc

    entries = [_entry_to_dict(entry) for entry in database.entries]
    entries.sort(key=lambda item: (item["author"], item["year"]))
    return entries


def load_citation_library(path: str) -> list[dict[str, str]]:
    """Parse a .bib file and persist it as the active library."""
    entries = parse_bib_file(path)
    _set_persisted_library_path(os.path.abspath(path))
    return entries


def get_active_library_entries() -> list[dict[str, str]]:
    """Return entries from the currently persisted library, if any."""
    path = get_persisted_library_path()
    if not path:
        return []
    try:
        return parse_bib_file(path)
    except CitationLibraryError:
        return []


def search_citations(
    query: str, limit: int = CITATION_MAX_RESULTS
) -> list[dict[str, str]]:
    """Search the active library by key, author, or title (case-insensitive)."""
    entries = get_active_library_entries()
    query = (query or "").strip().lower()
    if not query:
        return entries[:limit]

    matches = [
        entry
        for entry in entries
        if query in entry["key"].lower()
        or query in entry["author"].lower()
        or query in entry["title"].lower()
        or query in entry["year"]
    ]
    return matches[:limit]
