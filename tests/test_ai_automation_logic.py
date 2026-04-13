import unittest

from markdown_reader.logic import (
    build_ai_automation_fallback,
    get_ai_automation_task_templates,
)


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


if __name__ == "__main__":
    unittest.main()
