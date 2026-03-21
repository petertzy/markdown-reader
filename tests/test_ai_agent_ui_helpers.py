import unittest
from unittest.mock import patch

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

        ok, reason = app._validate_ai_action_payload(
            {
                "type": "replace_document",
                "content": "# New document\n\nBody",
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
            "old-doc": {"type": "replace_selection", "content": "x", "reason": "test"}
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
        self.assertEqual(app.ai_chat_pending_actions["new-doc"]["type"], "replace_selection")
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
                "type": "replace_selection",
                "content": "- Key point A\n- Key point B",
                "reason": "summary",
            },
        )

        self.assertIn("Here is your summary:", text)
        self.assertIn("Proposed content preview (replace_selection):", text)
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

    def test_append_ai_audit_log_caps_entries(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app.ai_action_audit_logs = []
        app._get_document_id_for_tab = lambda tab_index=None: "doc-1"

        with patch("markdown_reader.ui.AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES", 2), patch(
            "markdown_reader.ui.append_ai_automation_log"
        ) as mock_append:
            app._append_ai_audit_log("proposed", "replace_selection", content="a")
            app._append_ai_audit_log("applied", "replace_selection", content="b")
            app._append_ai_audit_log("rejected", "replace_selection", content="c")

        self.assertEqual(len(app.ai_action_audit_logs), 2)
        self.assertEqual(app.ai_action_audit_logs[-1]["status"], "rejected")
        self.assertEqual(mock_append.call_count, 3)

    def test_reject_ai_agent_action_clears_pending(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app.ai_chat_pending_actions = {
            "doc-1": {
                "type": "replace_selection",
                "content": "- item",
                "reason": "test",
                "action_id": "ai-1",
            }
        }
        app._get_document_id_for_tab = lambda tab_index=None: "doc-1"
        app._validate_ai_action_payload = lambda action: (True, "")
        app._render_current_chat_history = lambda: None
        status_calls = []

        class _StatusVar:
            def set(self, val):
                status_calls.append(val)

        app.ai_agent_status_var = _StatusVar()
        captured = {}

        def _append_log(**kwargs):
            captured.update(kwargs)

        app._append_ai_audit_log = _append_log

        with patch("markdown_reader.ui.messagebox.askyesno", return_value=True):
            app.reject_ai_agent_action()

        self.assertEqual(app.ai_chat_pending_actions["doc-1"]["type"], "none")
        self.assertEqual(status_calls[-1], "Suggestion rejected")
        self.assertEqual(captured["status"], "rejected")

    def test_show_ai_automation_log_loads_latest_ten(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app.ai_action_audit_logs = []

        logs = []
        for index in range(12):
            logs.append(
                {
                    "timestamp": f"2026-03-21T15:00:{index:02d}Z",
                    "status": "applied",
                    "action_type": "replace_selection",
                    "reason": f"r{index}",
                }
            )

        with patch("markdown_reader.ui.load_ai_automation_logs", return_value=logs) as mock_load, patch(
            "markdown_reader.ui.dialogs.Messagebox.show_info"
        ) as mock_show:
            app.show_ai_automation_log()

        mock_load.assert_called_once_with(limit=10)
        self.assertEqual(mock_show.call_count, 1)
        shown_text = mock_show.call_args[0][0]
        shown_lines = [line for line in shown_text.split("\n") if line.strip()]
        self.assertEqual(len(shown_lines), 10)
        self.assertIn("r2", shown_text)
        self.assertIn("r11", shown_text)


if __name__ == "__main__":
    unittest.main()
