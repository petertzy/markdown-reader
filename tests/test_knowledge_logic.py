from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend import knowledge_logic

NOTE_1 = """---
title: "Project Alpha Overview"
tags: [project, architecture]
---

# Project Alpha

Project Alpha is a next-generation distributed storage engine.

## Architecture

The system uses a decentralized peer-to-peer gossip protocol for node discovery.
Data is partitioned using consistent hashing across 1024 virtual buckets.

## Security Model

All inter-node traffic is encrypted with mTLS. Keys are rotated every 24 hours.
"""

NOTE_2 = """# Meeting Notes: May 2026

Discussion about Project Alpha timelines and milestones.

## Action Items

- Alice will finalize the consensus algorithm benchmarks.
- Bob will investigate SQLite FTS5 for local search indexing.
- Charlie will draft the research paper summary.
"""

NOTE_3 = """# Deep Learning Research

Survey of modern retrieval-augmented generation architectures.

## Dense vs Sparse Retrieval

Sparse retrieval using BM25 remains strong for exact keyword and entity recall.
Dense embeddings provide semantic generalization but require higher compute resources.
"""


class TestUtf8BomNotes(unittest.TestCase):
    """A UTF-8 BOM is category Cf, not whitespace, so str.strip() misses it."""

    BOM = "﻿"

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def _write(self, body: str, name: str = "note.md") -> Path:
        path = self.root / name
        path.write_bytes((self.BOM + body).encode("utf-8"))
        return path

    def _read_indexed(self, path: Path) -> str:
        """Read exactly the way index_knowledge_base does.

        This deliberately calls the encoding used in the indexing loop rather
        than hardcoding one, so reverting the fix actually fails these tests.
        """
        return path.read_text(
            encoding=knowledge_logic.NOTE_READ_ENCODING, errors="replace"
        )

    def test_bom_does_not_hide_the_first_heading(self):
        path = self._write("# My Note\n\nBody text.")
        title = knowledge_logic.extract_note_title(self._read_indexed(path), path.name)
        self.assertEqual(title, "My Note")

    def test_bom_does_not_hide_frontmatter(self):
        body = "---\ntitle: Real Title\ntags: [a]\n---\n\n# Heading\n\nBody."
        path = self._write(body)
        title = knowledge_logic.extract_note_title(self._read_indexed(path), path.name)
        self.assertEqual(title, "Real Title")

    def test_bom_frontmatter_is_not_chunked_as_body_text(self):
        body = "---\ntitle: Real Title\ntags: [a]\n---\n\n# Heading\n\nBody."
        path = self._write(body)
        chunks = knowledge_logic.chunk_markdown_document(
            self._read_indexed(path), str(path), path.name
        )
        for chunk in chunks:
            self.assertNotIn("title: Real Title", chunk["content"])
            self.assertNotIn("tags: [a]", chunk["content"])

    def test_indexing_bom_note_stores_clean_title_and_chunks(self):
        body = "---\ntitle: Real Title\ntags: [a]\n---\n\n# Heading\n\nBody."
        self._write(body)
        db_path = self.root / "knowledge.db"

        with mock.patch.object(
            knowledge_logic,
            "APP_SETTINGS_FILE_PATH",
            self.root / "settings.json",
        ):
            stats = knowledge_logic.index_knowledge_base(
                str(self.root), force=True, db_path=db_path
            )

        self.assertEqual(stats["total_files"], 1)
        notes = knowledge_logic.list_indexed_notes(db_path=db_path)
        self.assertEqual(notes[0]["title"], "Real Title")
        chunks = knowledge_logic.query_knowledge_base("Body", db_path=db_path)
        self.assertTrue(chunks)
        self.assertTrue(all("title: Real Title" not in c["content"] for c in chunks))

    def test_notes_without_a_bom_are_unchanged(self):
        path = self.root / "plain.md"
        path.write_text("# Plain Note\n\nBody.", encoding="utf-8")
        self.assertEqual(
            knowledge_logic.extract_note_title(
                path.read_text(encoding="utf-8-sig", errors="replace"), path.name
            ),
            "Plain Note",
        )

    def test_bom_only_file_does_not_crash(self):
        path = self.root / "bom.md"
        path.write_bytes(b"\xef\xbb\xbf")
        content = path.read_text(encoding="utf-8-sig", errors="replace")
        self.assertEqual(content, "")
        knowledge_logic.chunk_markdown_document(content, str(path), path.name)


class TestKnowledgeLogic(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.tmp_dir.name)

        # Create sample notes directory
        self.notes_dir = self.root_path / "notes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)

        self.note1_path = self.notes_dir / "project_alpha.md"
        self.note1_path.write_text(NOTE_1, encoding="utf-8")

        self.note2_path = self.notes_dir / "meetings.md"
        self.note2_path.write_text(NOTE_2, encoding="utf-8")

        # Subdirectory note
        sub_dir = self.notes_dir / "research"
        sub_dir.mkdir()
        self.note3_path = sub_dir / "rag_survey.markdown"
        self.note3_path.write_text(NOTE_3, encoding="utf-8")

        # Ignored directory note
        ignored_dir = self.notes_dir / ".git"
        ignored_dir.mkdir()
        (ignored_dir / "ignored.md").write_text("should be ignored", encoding="utf-8")

        # Set up isolated settings and DB paths
        self.settings_path = self.root_path / "settings.json"
        self.db_path = self.root_path / "knowledge_base.db"

        self._patcher_settings = mock.patch.object(
            knowledge_logic, "APP_SETTINGS_FILE_PATH", self.settings_path
        )
        self._patcher_db = mock.patch.object(
            knowledge_logic, "_get_db_file_path", return_value=self.db_path
        )
        self._patcher_settings.start()
        self._patcher_db.start()

    def tearDown(self):
        self._patcher_db.stop()
        self._patcher_settings.stop()
        self.tmp_dir.cleanup()

    def test_extract_note_title_from_frontmatter(self):
        title = knowledge_logic.extract_note_title(NOTE_1, "project_alpha.md")
        self.assertEqual(title, "Project Alpha Overview")

    def test_extract_note_title_from_heading(self):
        title = knowledge_logic.extract_note_title(NOTE_2, "meetings.md")
        self.assertEqual(title, "Meeting Notes: May 2026")

    def test_extract_note_title_fallback_filename(self):
        title = knowledge_logic.extract_note_title(
            "Just some notes without headings", "simple-notes.txt"
        )
        self.assertEqual(title, "simple notes")

    def test_chunk_markdown_document_creates_sections(self):
        chunks = knowledge_logic.chunk_markdown_document(
            NOTE_1, str(self.note1_path), "project_alpha.md"
        )
        self.assertGreaterEqual(len(chunks), 2)
        sections = [c["section"] for c in chunks]
        self.assertIn("Project Alpha > Architecture", sections)
        self.assertIn("Project Alpha > Security Model", sections)

    def test_chunk_markdown_document_preserves_nested_heading_path(self):
        chunks = knowledge_logic.chunk_markdown_document(
            "# Parent\n\nParent text.\n\n## Child\n\nChild text.\n\n### Grandchild\n\nDeep text.",
            str(self.note1_path),
            "project_alpha.md",
        )
        self.assertIn("Parent > Child", [chunk["section"] for chunk in chunks])
        self.assertIn(
            "Parent > Child > Grandchild", [chunk["section"] for chunk in chunks]
        )

    def test_extract_note_title_ignores_headings_inside_fenced_code(self):
        # A shell comment inside a fence is not a heading, so it must not be
        # mistaken for the note's title.
        content = (
            "Run this:\n\n```sh\n# Check disk\ndf -h\n```\n\n# Real Title\n\nBody.\n"
        )
        self.assertEqual(
            knowledge_logic.extract_note_title(content, "notes.md"), "Real Title"
        )

    def test_chunking_keeps_fenced_code_intact_and_out_of_the_section_tree(self):
        content = (
            "# Setup\n\nRun this:\n\n```bash\n# Install deps\npip install foo\n```\n\n"
            "## Config\n\nSet the key.\n"
        )
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "setup.md"
        )

        sections = [chunk["section"] for chunk in chunks]
        # The shell comment must not become a heading, nor the parent of a
        # later real section.
        self.assertIn("Setup", sections)
        self.assertIn("Setup > Config", sections)
        self.assertNotIn("Install deps", sections)
        self.assertNotIn("Install deps > Config", sections)

        # The fenced block stays whole in exactly one chunk, comment included.
        holding = [chunk for chunk in chunks if "pip install foo" in chunk["content"]]
        self.assertEqual(len(holding), 1)
        self.assertIn(
            "```bash\n# Install deps\npip install foo\n```", holding[0]["content"]
        )

    def test_chunking_ignores_tilde_fenced_code(self):
        content = "# Doc\n\n~~~\n# not a heading\n~~~\n\nSome text.\n"
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "doc.md"
        )
        sections = [chunk["section"] for chunk in chunks]
        self.assertEqual(set(sections), {"Doc"})
        self.assertTrue(
            any("not a heading" in chunk["content"] for chunk in chunks),
            "the fenced body must still be indexed as content",
        )

    def test_chunking_treats_an_unclosed_fence_as_code_to_end_of_document(self):
        # Matches CommonMark: an unterminated fence runs to the end of the file.
        content = "# Real Heading\n\n```\n# inside\n"
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "open.md"
        )
        self.assertEqual([chunk["section"] for chunk in chunks], ["Real Heading"])
        self.assertIn("# inside", chunks[0]["content"])

    def test_chunking_requires_matching_fence_length_and_character(self):
        content = (
            "# Doc\n\n````bash\n# inside\n```\n# still inside\n````\n\n## Next\nBody.\n"
        )
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "fences.md"
        )
        self.assertEqual([chunk["section"] for chunk in chunks], ["Doc", "Doc > Next"])
        self.assertIn("# still inside", chunks[0]["content"])

    def _large_fenced_document(self, opener: str, closer: str) -> str:
        # A section large enough that the paragraph-splitting chunker must
        # divide it (its own paragraph characters alone comfortably exceed
        # ``target_chunk_size``), whose code block contains blank lines
        # between statements.
        code_lines = []
        for i in range(90):
            code_lines.append(f"line {i}: sample code")
            code_lines.append("")
        return f"# Section\n\n{opener}\n" + "\n".join(code_lines) + f"\n{closer}\n"

    def test_large_fenced_code_block_is_not_split_at_internal_blank_lines(self):
        # A blank line inside a fenced block is code, not a paragraph break.
        # Splitting at those blank lines used to straddle the fence across
        # chunks, leaving one chunk with an orphaned ``` opener and the next
        # with a stray closer -- invalid Markdown fed to the AI prompt.
        content = self._large_fenced_document("```python", "```")
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "fences.md"
        )
        self.assertGreater(len(chunks), 0)

        # Every chunk keeps balanced fence markers.
        for chunk in chunks:
            self.assertEqual(chunk["content"].count("```") % 2, 0, chunk["content"])

        # The whole block survives in a single chunk.
        whole = [
            chunk
            for chunk in chunks
            if "line 0: sample code" in chunk["content"]
            and "line 89: sample code" in chunk["content"]
        ]
        self.assertEqual(len(whole), 1)

    def test_large_tilde_fenced_code_block_is_kept_whole(self):
        content = self._large_fenced_document("~~~", "~~~")
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "tildes.md"
        )
        self.assertGreater(len(chunks), 0)
        for chunk in chunks:
            self.assertEqual(chunk["content"].count("~~~") % 2, 0, chunk["content"])

    def test_large_prose_section_is_still_split_into_multiple_chunks(self):
        paragraph = "A full line of enough prose to fill a section. " * 8
        content = "# Section\n\n" + "\n\n".join(paragraph for _ in range(6)) + "\n"
        chunks = knowledge_logic.chunk_markdown_document(
            content, str(self.note1_path), "prose.md"
        )
        self.assertGreater(len(chunks), 1)

    def test_find_note_files_excludes_ignored_directories(self):
        found = knowledge_logic.find_note_files(self.notes_dir)
        paths = [p.name for p in found]
        self.assertIn("project_alpha.md", paths)
        self.assertIn("meetings.md", paths)
        self.assertIn("rag_survey.markdown", paths)
        self.assertNotIn("ignored.md", paths)

    def test_index_knowledge_base_indexes_all_notes(self):
        stats = knowledge_logic.index_knowledge_base(str(self.notes_dir), force=True)
        self.assertEqual(stats["total_files"], 3)
        self.assertGreater(stats["total_chunks"], 3)

        # Status check
        status = knowledge_logic.get_knowledge_base_status()
        self.assertEqual(status["file_count"], 3)
        self.assertTrue(status["exists"])

        # Notes list check
        notes = knowledge_logic.list_indexed_notes()
        self.assertEqual(len(notes), 3)

    def test_incremental_indexing_skips_unchanged_files(self):
        stats1 = knowledge_logic.index_knowledge_base(str(self.notes_dir), force=True)
        self.assertEqual(stats1["indexed_files"], 3)

        # Second indexing run should skip all unchanged files
        stats2 = knowledge_logic.index_knowledge_base(str(self.notes_dir), force=False)
        self.assertEqual(stats2["indexed_files"], 0)
        self.assertEqual(stats2["skipped_files"], 3)

        # Modify one file
        self.note1_path.write_text(
            NOTE_1 + "\n\n## New Section\nNew content here.", encoding="utf-8"
        )
        stats3 = knowledge_logic.index_knowledge_base(str(self.notes_dir), force=False)
        self.assertEqual(stats3["indexed_files"], 1)
        self.assertEqual(stats3["skipped_files"], 2)

    def test_index_expands_home_directory_and_removes_oversized_old_entry(self):
        with mock.patch.dict("os.environ", {"HOME": str(self.root_path)}):
            stats = knowledge_logic.index_knowledge_base("~/notes", force=True)
        self.assertEqual(stats["path"], str(self.notes_dir.resolve()))
        self.assertEqual(knowledge_logic.get_knowledge_base_status()["file_count"], 3)

        self.note1_path.write_bytes(b"x" * (5 * 1024 * 1024 + 1))
        with mock.patch.dict("os.environ", {"HOME": str(self.root_path)}):
            stats = knowledge_logic.index_knowledge_base("~/notes")
        self.assertEqual(stats["total_files"], 2)
        self.assertEqual(
            {note["rel_path"] for note in knowledge_logic.list_indexed_notes()},
            {"meetings.md", "research/rag_survey.markdown"},
        )

    def test_query_knowledge_base_finds_relevant_chunks(self):
        knowledge_logic.index_knowledge_base(str(self.notes_dir), force=True)

        # Search for Project Alpha architecture
        results = knowledge_logic.query_knowledge_base(
            "consistent hashing architecture", top_k=3
        )
        self.assertGreater(len(results), 0)
        self.assertIn("project_alpha.md", results[0]["rel_path"])
        self.assertIn("virtual buckets", results[0]["content"])

        # Search for Meeting action items
        results_meeting = knowledge_logic.query_knowledge_base(
            "Alice consensus benchmarks", top_k=3
        )
        self.assertGreater(len(results_meeting), 0)
        self.assertIn("meetings.md", results_meeting[0]["rel_path"])

        # Search for RAG survey
        results_rag = knowledge_logic.query_knowledge_base(
            "sparse retrieval BM25", top_k=3
        )
        self.assertGreater(len(results_rag), 0)
        self.assertIn("rag_survey.markdown", results_rag[0]["rel_path"])

    def test_build_knowledge_context_for_prompt(self):
        knowledge_logic.index_knowledge_base(str(self.notes_dir), force=True)
        results = knowledge_logic.query_knowledge_base("Project Alpha", top_k=2)
        context = knowledge_logic.build_knowledge_context_for_prompt(results)
        self.assertIn("Directory Knowledge Base Context", context)
        self.assertIn("project_alpha.md", context)

    def test_clear_knowledge_base(self):
        knowledge_logic.index_knowledge_base(str(self.notes_dir), force=True)
        status_before = knowledge_logic.get_knowledge_base_status()
        self.assertEqual(status_before["file_count"], 3)

        knowledge_logic.clear_knowledge_base()
        status_after = knowledge_logic.get_knowledge_base_status()
        self.assertEqual(status_after["file_count"], 0)
        self.assertEqual(status_after["chunk_count"], 0)
        self.assertEqual(status_after["path"], "")


class TestKnowledgeApiEndpoints(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from backend.main import app

        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.tmp_dir.name)

        self.notes_dir = self.root_path / "notes"
        self.notes_dir.mkdir(parents=True, exist_ok=True)
        (self.notes_dir / "note.md").write_text(
            "# Test Note\n\nSome important facts about Alpha.", encoding="utf-8"
        )

        self.settings_path = self.root_path / "settings.json"
        self.db_path = self.root_path / "knowledge_base.db"

        self._patcher_settings = mock.patch.object(
            knowledge_logic, "APP_SETTINGS_FILE_PATH", self.settings_path
        )
        self._patcher_db = mock.patch.object(
            knowledge_logic, "_get_db_file_path", return_value=self.db_path
        )
        self._patcher_settings.start()
        self._patcher_db.start()

        self.client = TestClient(app)

    def tearDown(self):
        self._patcher_db.stop()
        self._patcher_settings.stop()
        self.tmp_dir.cleanup()

    def test_api_index_and_status(self):
        # Index
        res = self.client.post(
            "/api/knowledge/index", json={"path": str(self.notes_dir), "force": True}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_files"], 1)

        # Status
        res_status = self.client.get("/api/knowledge/status")
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(res_status.json()["file_count"], 1)

        # Query
        res_query = self.client.post(
            "/api/knowledge/query", json={"query": "Alpha", "top_k": 2}
        )
        self.assertEqual(res_query.status_code, 200)
        qdata = res_query.json()
        self.assertEqual(qdata["count"], 1)
        self.assertIn("Alpha", qdata["results"][0]["content"])

        # Notes list
        res_notes = self.client.get("/api/knowledge/notes")
        self.assertEqual(res_notes.status_code, 200)
        self.assertEqual(res_notes.json()["count"], 1)

        # Toggle
        res_toggle = self.client.post("/api/knowledge/toggle", json={"enabled": False})
        self.assertEqual(res_toggle.status_code, 200)
        self.assertFalse(res_toggle.json()["enabled"])

        # Clear
        res_clear = self.client.delete("/api/knowledge/index")
        self.assertEqual(res_clear.status_code, 200)
        self.assertTrue(res_clear.json()["cleared"])

    def test_query_endpoint_bounds_top_k(self):
        self.assertEqual(
            self.client.post(
                "/api/knowledge/query", json={"query": "Alpha", "top_k": 0}
            ).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(
                "/api/knowledge/query", json={"query": "Alpha", "top_k": 21}
            ).status_code,
            422,
        )

    def test_ai_chat_with_knowledge_base_retrieval(self):
        # Index notes first
        self.client.post(
            "/api/knowledge/index", json={"path": str(self.notes_dir), "force": True}
        )

        # Mock _request_chat_from_provider and model getter to inspect knowledge_context
        with mock.patch(
            "backend.ai_logic._request_chat_from_provider",
            return_value="Here is info from your notes.",
        ) as mock_chat:
            with mock.patch(
                "backend.ai_logic._get_current_ai_provider", return_value="local"
            ):
                with mock.patch(
                    "backend.ai_logic._get_ai_model_for_request",
                    return_value="mock-model",
                ):
                    res = self.client.post(
                        "/api/ai/chat",
                        json={
                            "message": "Tell me about Alpha",
                            "use_knowledge_base": True,
                        },
                    )
                    self.assertEqual(res.status_code, 200)
                    data = res.json()
                    self.assertEqual(
                        data["assistant_message"], "Here is info from your notes."
                    )
                    self.assertEqual(len(data.get("used_sources", [])), 1)
                    self.assertEqual(data["used_sources"][0]["rel_path"], "note.md")

                    # Verify knowledge_context was injected into provider call
                    self.assertTrue(mock_chat.called)
                    kwargs = mock_chat.call_args.kwargs
                    self.assertIn(
                        "Directory Knowledge Base Context",
                        kwargs.get("knowledge_context", ""),
                    )

                    # A persisted OFF setting wins over a request asking for context.
                    knowledge_logic.set_knowledge_base_enabled(False)
                    res_disabled = self.client.post(
                        "/api/ai/chat",
                        json={
                            "message": "Tell me about Alpha",
                            "use_knowledge_base": True,
                        },
                    )
                    self.assertEqual(res_disabled.status_code, 200)
                    self.assertEqual(res_disabled.json().get("used_sources"), [])
                    self.assertEqual(
                        mock_chat.call_args.kwargs.get("knowledge_context"), ""
                    )


class TestFrontmatterDelimitersMustOwnTheirLine(unittest.TestCase):
    """A YAML frontmatter block ends at a ``---`` line, not at the next dashes.

    Locating the closing delimiter with a plain substring search also matches a
    run of dashes in the middle of a line, which ends the block early. The rest
    of the metadata is then treated as body text: it is prepended to the first
    indexed chunk, where it becomes searchable noise, and a ``title:`` value
    containing ``---`` is truncated mid-word.
    """

    # A dash run inside a metadata value. Nothing here is a delimiter.
    DASHES_IN_VALUE = (
        "---\n"
        "title: Groceries --- weekly\n"
        "tags: [home]\n"
        "---\n"
        "\n"
        "# Shopping\n"
        "\n"
        "Buy milk.\n"
    )

    def test_title_keeps_the_dash_run_inside_its_value(self):
        self.assertEqual(
            knowledge_logic.extract_note_title(self.DASHES_IN_VALUE, "shopping.md"),
            "Groceries --- weekly",
        )

    def test_trailing_metadata_never_reaches_the_chunk_text(self):
        chunks = knowledge_logic.chunk_markdown_document(
            self.DASHES_IN_VALUE, "/vault/shopping.md", "shopping.md"
        )
        indexed = "\n".join(chunk["content"] for chunk in chunks)
        self.assertIn("Buy milk.", indexed)
        for leaked in ("tags: [home]", "Groceries --- weekly", "title:"):
            self.assertNotIn(leaked, indexed)

    def test_body_after_the_real_delimiter_is_still_chunked(self):
        chunks = knowledge_logic.chunk_markdown_document(
            "---\ntitle: A --- B\n---\n\n# Real\n\nBody text.\n",
            "/vault/n.md",
            "n.md",
        )
        self.assertEqual([chunk["section"] for chunk in chunks], ["Real"])
        self.assertEqual(chunks[0]["content"], "Body text.")

    def test_several_dash_runs_in_one_block_do_not_truncate(self):
        note = "---\ntitle: A --- B --- C\nnote: x --- y\n---\n\n# H\n\nBody.\n"
        self.assertEqual(
            knowledge_logic.extract_note_title(note, "n.md"), "A --- B --- C"
        )

    def test_longer_dash_run_is_a_thematic_break_not_a_delimiter(self):
        # "----" is a horizontal rule in CommonMark, so a note that opens with
        # one has no frontmatter and the line must stay in the body.
        note = "----\ntitle: Not frontmatter\n----\n\n# Heading\n\nBody.\n"
        self.assertEqual(knowledge_logic.extract_note_title(note, "n.md"), "Heading")
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        self.assertEqual(chunks[0]["content"], "----\ntitle: Not frontmatter\n----")

    def test_dashes_followed_by_text_are_a_paragraph_not_a_delimiter(self):
        note = "--- not a delimiter\n\n# Heading\n\nBody.\n"
        self.assertEqual(knowledge_logic.extract_note_title(note, "n.md"), "Heading")
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        self.assertEqual(chunks[0]["content"], "--- not a delimiter")

    def test_unterminated_block_is_left_in_the_body(self):
        # YAML needs both delimiters; without one the whole note is content.
        note = "---\ntitle: Never closed\n\n# Heading\n\nBody.\n"
        self.assertEqual(knowledge_logic.extract_note_title(note, "n.md"), "Heading")
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        self.assertIn("title: Never closed", chunks[0]["content"])

    def test_crlf_notes_still_split(self):
        note = "---\r\ntitle: Windows Note\r\nnote: a --- b\r\n---\r\n\r\nBody.\r\n"
        self.assertEqual(
            knowledge_logic.extract_note_title(note, "n.md"), "Windows Note"
        )
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        self.assertEqual(chunks[0]["content"], "Body.")

    def test_closing_delimiter_may_carry_trailing_whitespace(self):
        note = "---\ntitle: Padded\n---   \n\nBody.\n"
        self.assertEqual(knowledge_logic.extract_note_title(note, "n.md"), "Padded")
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        self.assertEqual(chunks[0]["content"], "Body.")

    def test_empty_block_yields_no_frontmatter_and_keeps_the_body(self):
        chunks = knowledge_logic.chunk_markdown_document(
            "---\n---\n\n# Heading\n\nBody.\n", "/v/n.md", "n.md"
        )
        self.assertEqual([chunk["section"] for chunk in chunks], ["Heading"])
        self.assertEqual(chunks[0]["content"], "Body.")

    def test_split_frontmatter_returns_none_without_an_opening_line(self):
        for text in (
            "",
            "Body only.",
            "----\nnope\n----\n",
            "--- x\nnope\n",
            "---\nno closing delimiter\n",
            # Delimiters only ever count at the very start. A rule partway down
            # the note must not retroactively turn everything above it into
            # metadata, which would drop the opening prose from the index.
            "Meeting notes\n\n---\n\nAction items\n",
            "Intro.\n---\ntitle: x\n---\nrest\n",
        ):
            with self.subTest(text=text):
                self.assertIsNone(knowledge_logic._split_frontmatter(text))

    def test_a_rule_partway_down_the_note_keeps_the_prose_above_it(self):
        note = "Meeting notes\n\n---\n\nAction items\n"
        chunks = knowledge_logic.chunk_markdown_document(note, "/v/n.md", "n.md")
        indexed = "\n".join(chunk["content"] for chunk in chunks)
        self.assertIn("Meeting notes", indexed)
        self.assertIn("Action items", indexed)

    def test_an_indented_rule_is_not_a_delimiter(self):
        # The delimiter has to sit in column 0. An indented "---" is a rule
        # inside a list item, and must not close a frontmatter block.
        for text in (
            "  ---\ntitle: indented\n---\n\n# Heading\n\nBody.\n",
            "\t---\ntitle: tabbed\n---\n\n# Heading\n\nBody.\n",
        ):
            with self.subTest(text=text):
                self.assertIsNone(knowledge_logic._split_frontmatter(text))
                self.assertEqual(
                    knowledge_logic.extract_note_title(text, "n.md"), "Heading"
                )

    def test_split_frontmatter_returns_the_block_and_the_remainder(self):
        self.assertEqual(
            knowledge_logic._split_frontmatter("---\na: 1\nb: 2\n---\nrest\n"),
            ("a: 1\nb: 2", "rest\n"),
        )


class TestIndexingStoresCleanFrontmatterMetadata(unittest.TestCase):
    """End-to-end: what the parser returns is what lands in the database."""

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root_path = Path(self.tmp_dir.name)
        self.notes_dir = self.root_path / "notes"
        self.notes_dir.mkdir(parents=True)
        self.settings_path = self.root_path / "settings.json"
        self.db_path = self.root_path / "knowledge_base.db"
        self._patcher_settings = mock.patch.object(
            knowledge_logic, "APP_SETTINGS_FILE_PATH", self.settings_path
        )
        self._patcher_db = mock.patch.object(
            knowledge_logic, "_get_db_file_path", return_value=self.db_path
        )
        self._patcher_settings.start()
        self._patcher_db.start()

    def tearDown(self):
        self._patcher_db.stop()
        self._patcher_settings.stop()
        self.tmp_dir.cleanup()

    def _index(self, name, text):
        (self.notes_dir / name).write_text(text, encoding="utf-8")
        return knowledge_logic.index_knowledge_base(str(self.notes_dir))

    def test_indexed_title_and_chunks_are_free_of_stray_metadata(self):
        self._index(
            "shopping.md",
            "---\ntitle: Groceries --- weekly\ntags: [home]\n---\n\n"
            "# Shopping\n\nBuy milk.\n",
        )

        notes = knowledge_logic.list_indexed_notes(db_path=self.db_path)
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["title"], "Groceries --- weekly")

        hits = knowledge_logic.query_knowledge_base("tags", db_path=self.db_path)
        self.assertEqual(hits, [], "frontmatter leaked into the searchable chunks")

        hits = knowledge_logic.query_knowledge_base("milk", db_path=self.db_path)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["title"], "Groceries --- weekly")
        self.assertIn("Buy milk.", hits[0]["content"])

    def test_reindexing_a_rewritten_note_updates_the_stored_title(self):
        self._index("n.md", "---\ntitle: First --- draft\n---\n\nBody.\n")
        self._index("n.md", "---\ntitle: Second --- draft\n---\n\nBody.\n")

        notes = knowledge_logic.list_indexed_notes(db_path=self.db_path)
        self.assertEqual([note["title"] for note in notes], ["Second --- draft"])
        hits = knowledge_logic.query_knowledge_base("draft", db_path=self.db_path)
        self.assertEqual([hit["title"] for hit in hits], ["Second --- draft"])
