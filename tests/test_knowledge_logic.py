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
