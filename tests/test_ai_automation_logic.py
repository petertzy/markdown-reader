import unittest

from backend.ai_logic import (
    _apply_markdown_formatting_rules,
    _generate_lightweight_summary,
    _generate_markdown_toc,
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

    def test_fence_with_info_string_does_not_close_a_block(self):
        src = "```\n```python\n#still code\n```\n"
        self.assertEqual(_apply_markdown_formatting_rules(src), src)


class TestFencedHeadingsInGeneratedTOC(unittest.TestCase):
    """A ``#`` line inside a code fence is code, not a heading."""

    def test_toc_skips_hash_inside_backtick_fence(self):
        toc = _generate_markdown_toc("# Real\n\n```python\n# fake\n```\n\n## Second\n")
        self.assertNotIn("fake", toc)
        self.assertIn("- [Real](#real)", toc)
        self.assertIn("- [Second](#second)", toc)

    def test_toc_skips_hash_inside_tilde_fence(self):
        toc = _generate_markdown_toc("# A\n\n~~~bash\n## fake\n~~~\n\n## B\n")
        self.assertNotIn("fake", toc)
        self.assertIn("- [B](#b)", toc)

    def test_toc_ignores_longer_closing_fence_content(self):
        # A closing fence may be longer than the opener; the line between them
        # is still code.
        toc = _generate_markdown_toc("# A\n\n```\n# fake\n`````\n\n## B\n")
        self.assertNotIn("fake", toc)
        self.assertIn("- [B](#b)", toc)

    def test_toc_respects_fence_char_and_indent(self):
        for doc in (
            "# A\n\n   ```\n# fake\n   ```\n\n## B\n",  # up to 3 spaces = fence
            "# A\n\n```\n~~~\n# fake\n```\n\n## B\n",  # ~~~ inside ``` is code
            "# A\n\ntext `# not heading` more\n\n## B\n",  # inline span
            "# A\n\n    # indented\n\n## B\n",  # 4 spaces = code block, prose
        ):
            toc = _generate_markdown_toc(doc)
            self.assertNotIn("fake", toc, doc)
            self.assertNotIn("not-heading", toc, doc)
            self.assertIn("- [B](#b)", toc, doc)

    def test_unclosed_fence_swallows_remaining_headings(self):
        toc = _generate_markdown_toc("# A\n\n```\n# fake\n\n## also fake\n")
        self.assertIn("- [A](#a)", toc)
        self.assertNotIn("fake", toc)

    def test_summary_sections_skip_fenced_headings(self):
        summary = _generate_lightweight_summary(
            "# Real Title\n\nLead.\n\n```python\n# fake\n```\n\n## Second\n"
        )
        self.assertNotIn("fake", summary)
        self.assertIn("Real Title", summary)
        self.assertIn("Second", summary)

    def test_summary_lead_is_not_raw_code(self):
        # A document opening with a code block used to quote the commands back
        # as the opening sentence.
        summary = _generate_lightweight_summary(
            "```bash\nnpm install\n```\n\n# Setup\n\nRun the commands above.\n"
        )
        self.assertNotIn("npm install", summary)
        self.assertIn("Run the commands above.", summary)

    def test_summary_lead_skips_blank_line_inside_fenced_code(self):
        summary = _generate_lightweight_summary(
            "```text\nfirst command\n\nsecond command\n```\n\n# Setup\n\nReal introduction."
        )
        self.assertNotIn("first command", summary)
        self.assertNotIn("second command", summary)
        self.assertIn("Real introduction.", summary)

    def test_summary_without_any_prose_has_no_lead(self):
        summary = _generate_lightweight_summary("# Only\n\n```\ncode\n```\n")
        self.assertNotIn("code", summary)
        self.assertIn("Only", summary)


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


class TestTemplatePromptsReachTheirOwnHandler(unittest.TestCase):
    """The UI sends each template's own ``prompt``, not its ``id`` or a slash name.

    ``useSlashCommands.ts`` looks the template up by id and submits
    ``template.prompt`` verbatim, so ``build_ai_automation_fallback`` has to
    recognise the wording that is actually shipped. A template whose prompt
    matches no keyword silently fell through to the plain Markdown formatter,
    which left an unbalanced fence unbalanced and reported ``format_rules``.
    """

    def _dispatch(self, template_id, selected_text):
        template = next(
            item
            for item in get_ai_automation_task_templates()
            if item["id"] == template_id
        )
        result = build_ai_automation_fallback(
            template["prompt"],
            document_text="# Title\n\nBody text.",
            selected_text=selected_text,
        )
        self.assertIsNotNone(result, template_id)
        return result["proposed_action"]

    def test_fix_code_blocks_template_runs_the_fence_fixer(self):
        # "Format Markdown code fences and fix common fence syntax issues."
        # contains none of the original keywords ("format code", "code block",
        # "correct syntax", "fix code"), so this used to return format_rules.
        action = self._dispatch("fix_code_blocks", "```python\nprint(1)\n")
        self.assertEqual(action["reason"], "fix_code_blocks")
        self.assertEqual(action["content"], "```python\nprint(1)\n```")

    def test_fix_code_blocks_template_leaves_balanced_fences_alone(self):
        balanced = "```python\nprint(1)\n```"
        action = self._dispatch("fix_code_blocks", balanced)
        self.assertEqual(action["reason"], "fix_code_blocks")
        self.assertEqual(action["content"], balanced)

    def test_fix_code_template_asks_for_a_selection_when_there_is_none(self):
        # Reaching the code branch unlocks its own guard, which the formatter
        # branch never had.
        action = self._dispatch("fix_code_blocks", "")
        self.assertEqual(action["reason"], "selection_required_for_code_fix")
        self.assertEqual(action["type"], "none")

    def test_every_shipped_template_dispatches_to_its_own_handler(self):
        # The expected reason per template. format_selection shares the
        # formatter branch with a selection, which is correct.
        expected = {
            "format_selection": "format_rules",
            "generate_toc": "generate_toc",
            "generate_summary": "generate_summary",
            "fix_code_blocks": "fix_code_blocks",
        }
        self.assertEqual(
            {item["id"] for item in get_ai_automation_task_templates()},
            set(expected),
        )
        for template_id, reason in expected.items():
            with self.subTest(template_id=template_id):
                action = self._dispatch(template_id, "```python\nprint(1)\n")
                self.assertEqual(action["reason"], reason)

    def test_format_command_still_uses_the_formatter(self):
        # Guard against the fix over-reaching: adding "code fence" must not
        # divert ordinary /format requests into the fence fixer.
        result = build_ai_automation_fallback(
            "/format",
            document_text="#head\n\n-item\n",
            selected_text="#head\n\n-item\n",
        )
        self.assertEqual(result["proposed_action"]["reason"], "format_rules")
        self.assertEqual(result["proposed_action"]["content"], "# head\n\n- item\n")


class TestFormattingRulesPreserveThematicBreaks(unittest.TestCase):
    """A run of 3+ list markers is a thematic break, not a tight list item."""

    def test_thematic_break_is_not_split_into_a_list_item(self):
        # "---" is an <hr>; splitting it to "- -" destroys the rule.
        for src in (
            "Intro\n\n---\n\nOutro",
            "para\n\n***\n\npara2",
            "  ---\n",
            "- - -\n",
            "* * *\n",
        ):
            with self.subTest(src=src):
                self.assertEqual(_apply_markdown_formatting_rules(src), src)

    def test_yaml_frontmatter_delimiters_are_preserved(self):
        # "---" also delimits frontmatter, which the knowledge base parses
        # (backend/knowledge_logic.py extract_note_title).
        src = "---\ntitle: My Note\n---\n\nIntro paragraph.\n\n---\n\nOutro.\n"
        self.assertEqual(_apply_markdown_formatting_rules(src), src)

    def test_format_automation_preserves_thematic_breaks(self):
        # Reachable end-to-end: /format proposes a whole-document replacement.
        document = "Intro paragraph.\n\n---\n\nOutro paragraph.\n"
        result = build_ai_automation_fallback(
            "format", document_text=document, selected_text=""
        )

        self.assertIsNotNone(result)
        action = result["proposed_action"]
        self.assertEqual(action["type"], "replace_document")
        self.assertEqual(action["content"], document)

    def test_tight_list_items_are_still_normalised(self):
        # The genuine behaviour of the rule is unchanged.
        for src, want in (
            ("-item", "- item"),
            ("*item", "* item"),
            ("+item", "+ item"),
            ("  -nested", "  - nested"),
            ("1.item", "1. item"),
            ("#head", "# head"),
        ):
            with self.subTest(src=src):
                self.assertEqual(_apply_markdown_formatting_rules(src), want)


if __name__ == "__main__":
    unittest.main()
