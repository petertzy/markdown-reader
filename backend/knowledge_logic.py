"""
backend/knowledge_logic.py
===========================
Directory-level context and local RAG (Retrieval-Augmented Generation)
for personal notes and workspace Markdown documents.

This module provides:
  1. Discovery and parsing of Markdown/text files in a user-chosen folder.
  2. Smart chunking based on Markdown headings and paragraph structure.
  3. Fast, incremental indexing stored locally in SQLite with FTS5 BM25 search
     (and pure-Python keyword scoring fallback).
  4. Local retrieval to ground AI chat in personal notes without sending data
     to external vector databases.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Supported note file extensions
NOTE_EXTENSIONS = frozenset({".md", ".markdown", ".txt"})

# Notes are commonly authored or re-saved on Windows, which leaves a UTF-8 BOM.
# "utf-8-sig" strips it when present and behaves identically to "utf-8" when it
# is not. Without this the BOM sits in front of line 1 and breaks both the
# frontmatter "---" check and the first-heading match.
NOTE_READ_ENCODING = "utf-8-sig"
MAX_KNOWLEDGE_TOP_K = 20

# Directories to skip when scanning note vaults
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".obsidian",
        ".trash",
        ".vscode",
        ".idea",
        "node_modules",
        "__pycache__",
        ".venv",
        "venv",
        ".build",
        "dist",
        "build",
        ".next",
        ".tauri",
    }
)

_SETTINGS_KEY_KNOWLEDGE_PATH = "knowledge_base_path"
_SETTINGS_KEY_KNOWLEDGE_ENABLED = "knowledge_base_enabled"


def _get_settings_file_path() -> Path:
    """Return the shared desktop settings file path."""
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


def _get_db_file_path() -> Path:
    """Return the SQLite database path for local knowledge base storage."""
    return APP_SETTINGS_FILE_PATH.parent / "knowledge_base.db"


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


def get_persisted_knowledge_base_path() -> str:
    """Return the saved knowledge base directory path, or empty string."""
    return str(_load_app_settings().get(_SETTINGS_KEY_KNOWLEDGE_PATH, "")).strip()


def set_persisted_knowledge_base_path(path: str) -> None:
    """Persist the knowledge base directory path."""
    settings = _load_app_settings()
    settings[_SETTINGS_KEY_KNOWLEDGE_PATH] = path.strip()
    _save_app_settings(settings)


def get_knowledge_base_enabled() -> bool:
    """Return whether directory context is toggled on by default."""
    return bool(_load_app_settings().get(_SETTINGS_KEY_KNOWLEDGE_ENABLED, True))


def set_knowledge_base_enabled(enabled: bool) -> None:
    """Persist whether directory context is toggled on."""
    settings = _load_app_settings()
    settings[_SETTINGS_KEY_KNOWLEDGE_ENABLED] = bool(enabled)
    _save_app_settings(settings)


# ── Database Initialization ───────────────────────────────────────────────────


def _get_db_connection(db_path: Path | None = None) -> sqlite3.Connection:
    target = db_path or _get_db_file_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(target))
    con.row_factory = sqlite3.Row
    _init_db_schema(con)
    return con


def _supports_fts5(con: sqlite3.Connection) -> bool:
    try:
        cur = con.cursor()
        cur.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _test_fts USING fts5(x)")
        cur.execute("DROP TABLE IF EXISTS _test_fts")
        return True
    except Exception:
        return False


def _init_db_schema(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS indexed_files (
            path TEXT PRIMARY KEY,
            rel_path TEXT,
            title TEXT,
            mtime REAL,
            size INTEGER,
            chunk_count INTEGER DEFAULT 0
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT,
            rel_path TEXT,
            title TEXT,
            section TEXT,
            content TEXT,
            chunk_index INTEGER,
            FOREIGN KEY (file_path) REFERENCES indexed_files (path) ON DELETE CASCADE
        )
        """
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_file_path ON chunks (file_path)")

    if _supports_fts5(con):
        cur.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                title,
                section,
                content,
                rel_path,
                content='chunks',
                content_rowid='id'
            )
            """
        )
        # Create triggers to keep FTS in sync with chunks table
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
                INSERT INTO chunks_fts(rowid, title, section, content, rel_path)
                VALUES (new.id, new.title, new.section, new.content, new.rel_path);
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, title, section, content, rel_path)
                VALUES ('delete', old.id, old.title, old.section, old.content, old.rel_path);
            END;
            """
        )
        cur.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
                INSERT INTO chunks_fts(chunks_fts, rowid, title, section, content, rel_path)
                VALUES ('delete', old.id, old.title, old.section, old.content, old.rel_path);
                INSERT INTO chunks_fts(rowid, title, section, content, rel_path)
                VALUES (new.id, new.title, new.section, new.content, new.rel_path);
            END;
            """
        )
    con.commit()


# ── Document Parsing & Chunking ───────────────────────────────────────────────

_FRONTMATTER_DELIMITER = "---"


def _is_frontmatter_delimiter(line: str) -> bool:
    """Return whether a line is a bare ``---`` frontmatter delimiter.

    ``rstrip`` accepts harmless trailing whitespace, including the ``\\r`` from
    Windows ``\\r\\n`` endings, so Windows-authored notes still split. A longer
    run is *not* a delimiter:
    ``----`` is a thematic break, and ``--- text`` is a paragraph.
    """
    return line.rstrip() == _FRONTMATTER_DELIMITER


def _split_frontmatter(text: str) -> tuple[str, str] | None:
    """Split a leading YAML frontmatter block off a note.

    Returns ``(frontmatter, remainder)``, or ``None`` when the note does not open
    with a complete frontmatter block.

    Both delimiters have to be a line of their own. Searching for the next run of
    dashes anywhere in the text also matches one in the middle of a line, which
    ends the block early: the rest of the metadata is then treated as body text
    and prepended to the first indexed chunk.
    """
    lines = text.split("\n")
    if not lines or not _is_frontmatter_delimiter(lines[0]):
        return None
    for index in range(1, len(lines)):
        if _is_frontmatter_delimiter(lines[index]):
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    return None


def _markdown_fence(
    line: str, active: tuple[str, int] | None = None
) -> tuple[str, int] | None:
    stripped = line.strip()
    if not stripped or stripped[0] not in "`~":
        return None
    marker = stripped[0]
    length = len(stripped) - len(stripped.lstrip(marker))
    if length < 3:
        return None
    if active is None:
        return marker, length
    if marker != active[0] or length < active[1] or stripped[length:].strip():
        return None
    return marker, length


def _split_paragraphs(markdown: str) -> list[str]:
    """Split *markdown* on blank lines while keeping fenced blocks whole.

    A blank line between prose paragraphs separates them, but a blank line
    inside a fenced code block is part of the code. Splitting there would
    straddle the fence across chunks and leave one chunk with an orphaned
    opener and the next with a stray closer. The same ``_markdown_fence``
    rules used by the section scan apply here, so the two always agree.
    """
    paragraphs: list[str] = []
    current: list[str] = []
    active_fence: tuple[str, int] | None = None
    for line in markdown.split("\n"):
        fence = _markdown_fence(line, active_fence)
        if fence:
            active_fence = None if active_fence else fence
        if not line.strip() and active_fence is None:
            if current:
                paragraphs.append("\n".join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def extract_note_title(content: str, fallback_filename: str) -> str:
    """Extract a descriptive note title from frontmatter, first # heading, or filename."""
    # 1. Check YAML frontmatter: title: "..."
    frontmatter_split = _split_frontmatter(content)
    if frontmatter_split is not None:
        frontmatter = frontmatter_split[0]
        match = re.search(
            r"^title:\s*[\"']?(.*?)[\"']?\s*$",
            frontmatter,
            re.MULTILINE | re.IGNORECASE,
        )
        if match and match.group(1).strip():
            return match.group(1).strip()

    # 2. Check first Markdown heading, ignoring anything inside a fenced code
    #    block (a shell/YAML comment such as "# Install deps" is not a heading).
    active_fence: tuple[str, int] | None = None
    for line in content.splitlines():
        fence = _markdown_fence(line, active_fence)
        if fence:
            active_fence = None if active_fence else fence
            continue
        if active_fence:
            continue
        # A '#' that starts the line is a heading; an indented '#' (four
        # spaces) is an indented code block, exactly as the renderer treats it.
        if line.startswith("# "):
            title = line[2:].strip()
            if title:
                return title

    # 3. Fallback to clean filename
    name = Path(fallback_filename).stem
    return name.replace("_", " ").replace("-", " ").strip() or fallback_filename


def chunk_markdown_document(
    content: str,
    file_path: str,
    rel_path: str,
    target_chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> list[dict[str, Any]]:
    """
    Split a Markdown document into contextual chunks organized by section headings.

    Preserves heading context for each chunk (e.g. "Section > Subsection").
    """
    text = content.strip("\n").rstrip()
    if not text:
        return []

    title = extract_note_title(text, os.path.basename(file_path))

    # Strip YAML frontmatter if present for chunking
    body = text
    frontmatter_split = _split_frontmatter(body)
    if frontmatter_split is not None:
        body = frontmatter_split[1].strip("\n").rstrip()

    lines = body.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_section = "Overview"
    heading_stack: list[tuple[int, str]] = []
    current_lines: list[str] = []

    active_fence: tuple[str, int] | None = None
    for line in lines:
        fence = _markdown_fence(line, active_fence)
        if fence:
            # A fence marker is content, never a section boundary, and the lines
            # it wraps must not be scanned for headings.
            active_fence = None if active_fence else fence
            current_lines.append(line)
            continue
        if active_fence:
            current_lines.append(line)
            continue
        # Match the raw line, not its stripped form: a '#' that is indented by
        # four spaces opens an indented code block, not a heading.
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            if current_lines:
                sections.append((current_section, current_lines))
                current_lines = []
            level = len(heading_match.group(1))
            heading = heading_match.group(2).strip()
            heading_stack = [
                (depth, name) for depth, name in heading_stack if depth < level
            ]
            heading_stack.append((level, heading))
            current_section = " > ".join(name for _, name in heading_stack)
            continue
        current_lines.append(line)

    if current_lines:
        sections.append((current_section, current_lines))

    chunks: list[dict[str, Any]] = []
    chunk_index = 0

    for section_name, sec_lines in sections:
        sec_text = "\n".join(sec_lines).strip("\n").rstrip()
        if not sec_text:
            continue

        # If section is small enough, keep as single chunk
        if len(sec_text) <= target_chunk_size:
            chunks.append(
                {
                    "file_path": file_path,
                    "rel_path": rel_path,
                    "title": title,
                    "section": section_name,
                    "content": sec_text,
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1
            continue

        # Split larger section by paragraphs. Blank lines inside a fenced
        # code block are code, not paragraph boundaries.
        paragraphs = _split_paragraphs(sec_text)
        current_chunk_parts: list[str] = []
        current_len = 0

        for para in paragraphs:
            para = para.strip("\n").rstrip()
            if not para:
                continue

            para_len = len(para)
            if current_len + para_len > target_chunk_size and current_chunk_parts:
                chunk_str = "\n\n".join(current_chunk_parts)
                chunks.append(
                    {
                        "file_path": file_path,
                        "rel_path": rel_path,
                        "title": title,
                        "section": section_name,
                        "content": chunk_str,
                        "chunk_index": chunk_index,
                    }
                )
                chunk_index += 1
                # Overlap: keep the last paragraph if reasonable
                if len(current_chunk_parts[-1]) < chunk_overlap:
                    current_chunk_parts = [current_chunk_parts[-1], para]
                    current_len = len(current_chunk_parts[0]) + para_len
                else:
                    current_chunk_parts = [para]
                    current_len = para_len
            else:
                current_chunk_parts.append(para)
                current_len += para_len

        if current_chunk_parts:
            chunks.append(
                {
                    "file_path": file_path,
                    "rel_path": rel_path,
                    "title": title,
                    "section": section_name,
                    "content": "\n\n".join(current_chunk_parts),
                    "chunk_index": chunk_index,
                }
            )
            chunk_index += 1

    return chunks


# ── Directory Indexing ────────────────────────────────────────────────────────


def find_note_files(directory: str | Path) -> list[Path]:
    """Scan a directory recursively for Markdown and text notes, skipping ignored folders."""
    base = Path(directory).resolve()
    if not base.is_dir():
        return []

    note_paths: list[Path] = []
    for root, dirs, files in os.walk(base):
        # Exclude ignored directories in-place so os.walk doesn't descend into them
        dirs[:] = [
            d for d in dirs if d not in IGNORED_DIRECTORIES and not d.startswith(".")
        ]

        for file in files:
            if file.startswith("."):
                continue
            ext = os.path.splitext(file)[1].lower()
            if ext in NOTE_EXTENSIONS:
                note_paths.append(Path(root) / file)

    return note_paths


def index_knowledge_base(
    directory: str,
    force: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """
    Scan and index all Markdown notes in the given folder incrementally.

    Returns statistics about the indexing run.
    """
    base_path = Path(directory).expanduser().resolve()
    if not base_path.is_dir():
        raise ValueError(f"Directory does not exist or is not a folder: {directory}")

    start_time = time.time()
    con = _get_db_connection(db_path)
    try:
        cur = con.cursor()

        # Track currently existing files in DB
        existing_records: dict[str, tuple[float, int]] = {}
        if not force:
            cur.execute("SELECT path, mtime, size FROM indexed_files")
            for row in cur.fetchall():
                existing_records[row["path"]] = (row["mtime"], row["size"])
        else:
            cur.execute("DELETE FROM chunks")
            cur.execute("DELETE FROM indexed_files")
            con.commit()

        note_files = find_note_files(base_path)
        current_paths: set[str] = set()

        files_indexed = 0
        files_skipped = 0
        total_chunks_created = 0

        for note_path in note_files:
            full_path_str = str(note_path)
            current_paths.add(full_path_str)

            try:
                stat = note_path.stat()
                mtime = stat.st_mtime
                size = stat.st_size

                # Skip large files (> 5MB)
                if size > 5 * 1024 * 1024:
                    # Treat it as absent so cleanup removes any older indexed copy.
                    current_paths.discard(full_path_str)
                    continue

                # Check if file has changed
                if not force and full_path_str in existing_records:
                    prev_mtime, prev_size = existing_records[full_path_str]
                    if abs(prev_mtime - mtime) < 1e-4 and prev_size == size:
                        files_skipped += 1
                        continue

                # Read and process note.
                # "utf-8-sig" rather than "utf-8": a BOM (U+FEFF) is category Cf,
                # not whitespace, so str.strip() does not remove it. It would
                # sit in front of the first line and break both the frontmatter
                # "---" check and the heading match, silently falling back to the
                # filename and injecting raw frontmatter into the chunk text.
                try:
                    content = note_path.read_text(
                        encoding=NOTE_READ_ENCODING, errors="replace"
                    )
                except Exception as read_err:
                    logger.warning(
                        "Could not read note file %s: %s", full_path_str, read_err
                    )
                    continue

                rel_path = str(note_path.relative_to(base_path))
                title = extract_note_title(content, note_path.name)
                chunks = chunk_markdown_document(content, full_path_str, rel_path)

                # Clear old chunks for this file if updating
                cur.execute("DELETE FROM chunks WHERE file_path = ?", (full_path_str,))

                # Insert new chunks
                for ch in chunks:
                    cur.execute(
                        """
                        INSERT INTO chunks (file_path, rel_path, title, section, content, chunk_index)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            ch["file_path"],
                            ch["rel_path"],
                            ch["title"],
                            ch["section"],
                            ch["content"],
                            ch["chunk_index"],
                        ),
                    )

                # Update indexed_files record
                cur.execute(
                    """
                    INSERT OR REPLACE INTO indexed_files (path, rel_path, title, mtime, size, chunk_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (full_path_str, rel_path, title, mtime, size, len(chunks)),
                )

                files_indexed += 1
                total_chunks_created += len(chunks)

            except Exception as file_err:
                logger.warning("Error processing note %s: %s", full_path_str, file_err)

        # Clean up files that were deleted from disk
        removed_count = 0
        if not force:
            for old_path in existing_records:
                if old_path not in current_paths:
                    cur.execute("DELETE FROM chunks WHERE file_path = ?", (old_path,))
                    cur.execute("DELETE FROM indexed_files WHERE path = ?", (old_path,))
                    removed_count += 1

        # Update metadata
        cur.execute(
            "INSERT OR REPLACE INTO knowledge_meta (key, value) VALUES ('root_path', ?)",
            (str(base_path),),
        )
        cur.execute(
            "INSERT OR REPLACE INTO knowledge_meta (key, value) VALUES ('last_indexed_at', ?)",
            (str(time.time()),),
        )

        con.commit()

        # Get total stats
        cur.execute("SELECT COUNT(*) FROM indexed_files")
        total_files = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM chunks")
        total_chunks = cur.fetchone()[0]

        # Save to user settings
        set_persisted_knowledge_base_path(str(base_path))

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "path": str(base_path),
            "total_files": total_files,
            "indexed_files": files_indexed,
            "skipped_files": files_skipped,
            "removed_files": removed_count,
            "total_chunks": total_chunks,
            "duration_ms": duration_ms,
        }
    finally:
        con.close()


def get_knowledge_base_status(db_path: Path | None = None) -> dict[str, Any]:
    """Return status and statistics for the active knowledge base."""
    persisted_path = get_persisted_knowledge_base_path()
    path_exists = bool(persisted_path and os.path.isdir(persisted_path))

    db_target = db_path or _get_db_file_path()
    if not db_target.exists():
        return {
            "path": persisted_path,
            "exists": path_exists,
            "enabled": get_knowledge_base_enabled(),
            "file_count": 0,
            "chunk_count": 0,
            "last_indexed_at": None,
        }

    try:
        con = _get_db_connection(db_target)
        try:
            cur = con.cursor()
            cur.execute("SELECT COUNT(*) FROM indexed_files")
            file_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cur.fetchone()[0]
            cur.execute(
                "SELECT value FROM knowledge_meta WHERE key = 'last_indexed_at'"
            )
            last_row = cur.fetchone()
            last_indexed_at = (
                float(last_row["value"]) if last_row and last_row["value"] else None
            )
        finally:
            con.close()
    except Exception:
        file_count = 0
        chunk_count = 0
        last_indexed_at = None

    return {
        "path": persisted_path,
        "exists": path_exists,
        "enabled": get_knowledge_base_enabled(),
        "file_count": file_count,
        "chunk_count": chunk_count,
        "last_indexed_at": last_indexed_at,
    }


def list_indexed_notes(
    limit: int = 100, db_path: Path | None = None
) -> list[dict[str, Any]]:
    """Return a list of all indexed notes in the knowledge base."""
    db_target = db_path or _get_db_file_path()
    if not db_target.exists():
        return []

    try:
        con = _get_db_connection(db_target)
        try:
            cur = con.cursor()
            cur.execute(
                """
                SELECT path, rel_path, title, mtime, size, chunk_count
                FROM indexed_files
                ORDER BY mtime DESC
                LIMIT ?
                """,
                (limit,),
            )
            return [dict(row) for row in cur.fetchall()]
        finally:
            con.close()
    except Exception:
        return []


def clear_knowledge_base(db_path: Path | None = None) -> None:
    """Clear all indexed data and reset knowledge base."""
    db_target = db_path or _get_db_file_path()
    if db_target.exists():
        try:
            con = _get_db_connection(db_target)
            try:
                cur = con.cursor()
                cur.execute("DELETE FROM chunks")
                cur.execute("DELETE FROM indexed_files")
                cur.execute("DELETE FROM knowledge_meta")
                con.commit()
            finally:
                con.close()
        except Exception as exc:
            logger.warning("Error clearing knowledge base tables: %s", exc)

    set_persisted_knowledge_base_path("")


# ── Search & Retrieval (RAG) ──────────────────────────────────────────────────


def _sanitize_fts_query(query: str) -> str:
    """Clean and prepare a natural language query for SQLite FTS5."""
    # Remove FTS special operator characters
    cleaned = re.sub(r'["\'*^:()\[\]{}]', " ", query)
    tokens = [t.strip() for t in cleaned.split() if len(t.strip()) > 1]
    if not tokens:
        return ""
    # Join with OR for broad keyword matching
    return " OR ".join(f'"{t}"' for t in tokens)


def _python_keyword_search(
    con: sqlite3.Connection, query: str, top_k: int
) -> list[dict[str, Any]]:
    """Fallback in-memory keyword scoring when FTS5 is not available or query errors."""
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 1]
    if not words:
        return []

    cur = con.cursor()
    cur.execute("SELECT id, file_path, rel_path, title, section, content FROM chunks")
    rows = cur.fetchall()

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        title = (row["title"] or "").lower()
        section = (row["section"] or "").lower()
        content = (row["content"] or "").lower()

        score = 0.0
        for w in words:
            if w in title:
                score += 3.0
            if w in section:
                score += 2.0
            if w in content:
                score += 1.0

        if score > 0:
            item = dict(row)
            item["score"] = score
            scored.append((score, item))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item for _, item in scored[:top_k]]


def query_knowledge_base(
    query: str,
    top_k: int = 5,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """
    Search the local knowledge base for chunks most relevant to the query.

    Uses FTS5 BM25 relevance scoring where available, falling back to keyword scoring.
    """
    q = (query or "").strip()
    if not q:
        return []
    top_k = max(1, min(int(top_k), MAX_KNOWLEDGE_TOP_K))

    db_target = db_path or _get_db_file_path()
    if not db_target.exists():
        return []

    con = _get_db_connection(db_target)
    try:
        cur = con.cursor()

        if _supports_fts5(con):
            fts_query = _sanitize_fts_query(q)
            if fts_query:
                try:
                    cur.execute(
                        """
                        SELECT c.id, c.file_path, c.rel_path, c.title, c.section, c.content,
                               bm25(chunks_fts, 2.5, 1.8, 1.0, 1.5) AS rank
                        FROM chunks_fts f
                        JOIN chunks c ON f.rowid = c.id
                        WHERE chunks_fts MATCH ?
                        ORDER BY rank ASC
                        LIMIT ?
                        """,
                        (fts_query, top_k),
                    )
                    results = [dict(row) for row in cur.fetchall()]
                    if results:
                        return results
                except Exception as fts_err:
                    logger.debug(
                        "FTS5 query failed (%s), falling back to keyword search",
                        fts_err,
                    )

        # Fallback to python keyword search
        return _python_keyword_search(con, q, top_k)
    finally:
        con.close()


def build_knowledge_context_for_prompt(
    chunks: list[dict[str, Any]], max_chars: int = 4000
) -> str:
    """Format retrieved knowledge chunks into context text to inject into an AI prompt."""
    if not chunks:
        return ""

    parts = [
        "### Directory Knowledge Base Context (Local Personal Notes):",
        "The following notes from the user's workspace are relevant to the query. "
        "Use them to answer accurately, citing note names/sections where helpful:\n",
    ]

    total_len = sum(len(p) for p in parts)
    for i, ch in enumerate(chunks, 1):
        rel_path = ch.get("rel_path") or os.path.basename(
            ch.get("file_path", "note.md")
        )
        title = ch.get("title", rel_path)
        section = ch.get("section", "")
        sec_header = f" > {section}" if section and section != "Overview" else ""
        content = ch.get("content", "").strip("\n")

        block = f"--- [Source {i}: {rel_path} ({title}{sec_header})] ---\n{content}\n"
        if total_len + len(block) > max_chars and i > 1:
            # Reached context budget limit
            break
        parts.append(block)
        total_len += len(block)

    return "\n".join(parts)
