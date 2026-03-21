import unittest

from markdown_reader.ui import MarkdownReader


class TestAIAgentUIHelpers(unittest.TestCase):
    def test_validate_action_payload_accepts_supported_actions(self):
        app = MarkdownReader.__new__(MarkdownReader)

        ok, reason = app._validate_ai_action_payload(
            {
                "type": "replace_selection",
                "content": "# Updated section\n",
            }
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

        ok, reason = app._validate_ai_action_payload(
            {
                "type": "insert_at_cursor",
                "content": "\n- New bullet\n",
            }
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")

    def test_validate_action_payload_rejects_invalid_inputs(self):
        app = MarkdownReader.__new__(MarkdownReader)

        ok, _ = app._validate_ai_action_payload(None)
        self.assertFalse(ok)

        ok, _ = app._validate_ai_action_payload({"type": "none", "content": "x"})
        self.assertFalse(ok)

        ok, _ = app._validate_ai_action_payload({"type": "replace_selection", "content": ""})
        self.assertFalse(ok)

        ok, _ = app._validate_ai_action_payload(
            {"type": "replace_selection", "content": "abc\x00def"}
        )
        self.assertFalse(ok)

        ok, _ = app._validate_ai_action_payload(
            {"type": "insert_at_cursor", "content": "x" * 20001}
        )
        self.assertFalse(ok)

    def test_migrate_chat_document_key_moves_history_and_action(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app.ai_chat_histories = {
            "old-doc": [{"role": "user", "content": "hello"}],
            "new-doc": [{"role": "assistant", "content": "existing"}],
        }
        app.ai_chat_pending_actions = {
            "old-doc": {"type": "insert_at_cursor", "content": "x", "reason": "test"}
        }
        persist_calls = {"count": 0}
        app._persist_ai_chat_histories = lambda: persist_calls.__setitem__("count", persist_calls["count"] + 1)

        app._migrate_chat_document_key("old-doc", "new-doc")

        self.assertNotIn("old-doc", app.ai_chat_histories)
        self.assertEqual(
            app.ai_chat_histories["new-doc"],
            [
                {"role": "assistant", "content": "existing"},
                {"role": "user", "content": "hello"},
            ],
        )
        self.assertNotIn("old-doc", app.ai_chat_pending_actions)
        self.assertEqual(app.ai_chat_pending_actions["new-doc"]["type"], "insert_at_cursor")
        self.assertEqual(persist_calls["count"], 1)

    def test_migrate_chat_document_key_noop_when_invalid(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app.ai_chat_histories = {"same": [{"role": "user", "content": "msg"}]}
        app.ai_chat_pending_actions = {}
        persist_calls = {"count": 0}
        app._persist_ai_chat_histories = lambda: persist_calls.__setitem__("count", persist_calls["count"] + 1)

        app._migrate_chat_document_key("same", "same")
        app._migrate_chat_document_key("", "new")
        app._migrate_chat_document_key("old", "")

        self.assertEqual(app.ai_chat_histories["same"][0]["content"], "msg")
        self.assertEqual(persist_calls["count"], 0)

    def test_compose_assistant_chat_text_includes_action_preview(self):
        app = MarkdownReader.__new__(MarkdownReader)

        text = app._compose_assistant_chat_text(
            "Here is your summary:",
            {
                "type": "insert_at_cursor",
                "content": "- Key point A\n- Key point B",
                "reason": "summary",
            },
        )

        self.assertIn("Here is your summary:", text)
        self.assertIn("Proposed content preview (insert_at_cursor):", text)
        self.assertIn("- Key point A", text)

    def test_compose_assistant_chat_text_skips_duplicate_preview_when_same_content(self):
        app = MarkdownReader.__new__(MarkdownReader)

        summary = (
            "Markdown Reader is a cross-platform Markdown editor built with "
            "Python and Tkinter, featuring preview, translation, AI chat, and PDF tools."
        )
        text = app._compose_assistant_chat_text(
            summary,
            {
                "type": "replace_selection",
                "content": summary,
                "reason": "summary",
            },
        )

        self.assertEqual(text, summary)
        self.assertNotIn("Proposed content preview", text)


if __name__ == "__main__":
    unittest.main()
