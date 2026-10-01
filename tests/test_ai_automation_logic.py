import unittest

from backend.ai_logic import (
    _apply_markdown_formatting_rules,
    build_ai_automation_fallback,
    get_ai_automation_task_templates,
)


class TestFormattingRulesSkipFencedCode(unittest.TestCase):
    """/format must never rewrite lines inside a fenced code block."""

    def test_shebang_is_not_turned_into_a_heading(self):
        src = "```bash\n#!/usr/bin/env bash\nset -euo pipefail\n```"
        self.assertEqual(_apply_markdown_formatting_rules(src), src)

    def test_numeric_literal_is_not_split(self):
        # The ordered-list rule turned the float 1.5 into "1. 5".
        self.assertEqual(
            _apply_markdown_formatting_rules("```\n1.5\n```"), "```\n1.5\n```"
        )

    def test_comments_and_tilde_fences_are_untouched(self):
        for src in (
            "```python\n#comment\nx=1\n```",
            "```yaml\n#cfg: true\n```",
            "~~~bash\n#!/bin/sh\necho -n hi\n~~~",
            "```\n    # indented comment\n    2.75\n```",
        ):
            self.assertEqual(_apply_markdown_formatting_rules(src), src, src)

    def test_prose_normalisation_is_unchanged(self):
        # The rules still apply outside fences, byte-for-byte as before.
        for src, want in (
            ("#heading", "# heading"),
            ("####deep", "#### deep"),
            ("-item", "- item"),
            ("*star", "* star"),
            ("1.item", "1. item"),
            ("   ###x", "   ###x"),
        ):
            self.assertEqual(_apply_markdown_formatting_rules(src), want, src)

    def test_prose_around_a_fence_is_still_normalised(self):
        src = "#heading\n\n```\n#!not a heading\n```\n\n-tail\n"
        self.assertEqual(
            _apply_markdown_formatting_rules(src),
            "# heading\n\n```\n#!not a heading\n```\n\n- tail\n",
        )

    def test_unclosed_fence_protects_the_rest(self):
        src = "```\n#!/bin/sh\n#still code\n"
        self.assertEqual(_apply_markdown_formatting_rules(src), src)

    def test_tilde_inside_backtick_fence_is_code(self):
        src = "```\n~~~\n#!/bin/sh\n```"
        self.assertEqual(_apply_markdown_formatting_rules(src), src)


class TestAIAutomationLogic(unittest.TestCase):
    def test_templates_are_available(self):
        templates = get_ai_automation_task_templates()
        template_ids = {item["id"] for item in templates}

        self.assertIn("format_selection", template_ids)
        self.assertIn("generate_toc", template_ids)
        self.assertIn("generate_summary", template_ids)
        self.assertIn("fix_code_blocks", template_ids)

    def test_toc_fallback_generates_replace_action_with_selection(self):
        markdown_text = "# Title\n\n## Section A\nText\n\n### Details\n"
        result = build_ai_automation_fallback(
            "generate table of contents",
            document_text=markdown_text,
            selected_text="TOC",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_selection")
        self.assertIn("## Table of Contents", result["proposed_action"]["content"])
        self.assertIn("- [Title](#title)", result["proposed_action"]["content"])

    def test_toc_fallback_full_document_without_selection(self):
        result = build_ai_automation_fallback(
            "generate table of contents",
            document_text="# Title\n\n## Section\nText",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_document")
        self.assertEqual(
            result["proposed_action"]["reason"], "generate_toc_full_document"
        )
        self.assertIn("## Table of Contents", result["proposed_action"]["content"])

    def test_code_block_fallback_closes_unbalanced_fence(self):
        selected_text = "```\ndef hello():\n    return 1\n"
        result = build_ai_automation_fallback(
            "format code blocks and correct syntax",
            document_text="",
            selected_text=selected_text,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_selection")
        self.assertTrue(result["proposed_action"]["content"].strip().endswith("```"))

    def test_template_list_fallback_returns_no_action(self):
        result = build_ai_automation_fallback(
            "show task templates",
            document_text="# Doc",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "none")
        self.assertIn("Available automation templates", result["assistant_message"])

    def test_format_fallback_full_document_without_selection(self):
        result = build_ai_automation_fallback(
            "format this section",
            document_text="# Title\nText",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_document")
        self.assertEqual(
            result["proposed_action"]["reason"], "format_rules_full_document"
        )
        self.assertIn("# Title", result["proposed_action"]["content"])

    def test_summary_without_selection_still_returns_summary_text(self):
        markdown_text = "# Title\n\nThis is a test document for summary generation."
        result = build_ai_automation_fallback(
            "generate summary",
            document_text=markdown_text,
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_document")
        self.assertEqual(
            result["proposed_action"]["reason"], "generate_summary_full_document"
        )
        self.assertIn("## Summary", result["proposed_action"]["content"])
        self.assertTrue(result["assistant_message"].startswith("## Summary"))
        self.assertEqual(
            result["proposed_action"]["content"], result["assistant_message"]
        )

    def test_summary_without_document_content_returns_no_content_message(self):
        result = build_ai_automation_fallback(
            "generate summary",
            document_text="",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "none")
        self.assertEqual(result["proposed_action"]["reason"], "no_content_for_summary")
        self.assertIn("No document content", result["assistant_message"])

    def test_slash_summary_command_uses_summary_fallback(self):
        result = build_ai_automation_fallback(
            "/summarize",
            document_text="# Title\n\nThis is a test document.",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_document")
        self.assertIn("## Summary", result["assistant_message"])

    def test_slash_toc_command_uses_toc_fallback(self):
        result = build_ai_automation_fallback(
            "/toc",
            document_text="# Title\n\n## Section",
            selected_text="",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_document")
        self.assertIn("## Table of Contents", result["proposed_action"]["content"])

    def test_slash_fix_code_command_uses_code_fallback(self):
        result = build_ai_automation_fallback(
            "/fix-code",
            document_text="",
            selected_text="```\nprint('hello')\n",
        )

        self.assertIsNotNone(result)
        self.assertEqual(result["proposed_action"]["type"], "replace_selection")
        self.assertTrue(result["proposed_action"]["content"].strip().endswith("```"))


if __name__ == "__main__":
    unittest.main()
