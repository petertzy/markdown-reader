import tkinter as tk
import unittest
from unittest.mock import patch

from markdown_reader.ui import MarkdownReader


class _SimpleVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value

    def set(self, value):
        self._value = value


class _FakeInputBox:
    def __init__(self, text):
        self._text = text
        self.delete_calls = 0

    def get(self, _start, _end):
        return self._text

    def delete(self, _start, _end):
        self.delete_calls += 1
        self._text = ""


class _FakeTextAreaNoSelection:
    def get(self, start, end):
        if start == "sel.first" and end == "sel.last":
            raise tk.TclError("no selection")
        return "document body"


class _FakeNotebook:
    def select(self):
        return "tab-0"

    def index(self, _selected):
        return 0


class TestSelectionOnlyModeIntegration(unittest.TestCase):
    def test_selection_only_without_selection_shows_error_and_stops(self):
        app = MarkdownReader.__new__(MarkdownReader)
        app._chat_busy = False
        app.notebook = _FakeNotebook()
        app.tab_document_ids = ["doc-1"]
        app.ai_chat_histories = {"doc-1": []}
        app.ai_chat_input_box = _FakeInputBox("format this section")
        app.ai_chat_context_mode_var = _SimpleVar("selection")

        app.get_current_text_area = lambda: _FakeTextAreaNoSelection()
        app._get_document_id_for_tab = lambda tab_index=None: "doc-1"

        append_called = {"value": False}

        def _append_chat_message(*_args, **_kwargs):
            append_called["value"] = True

        app._append_chat_message = _append_chat_message

        with patch("markdown_reader.ui.dialogs.Messagebox.show_info") as mock_show_info:
            app.send_ai_agent_message()

        mock_show_info.assert_called_once_with(
            "AI Agent",
            "Selection-only mode is enabled. Please select text first.",
        )
        self.assertFalse(app._chat_busy)
        self.assertEqual(app.ai_chat_input_box.delete_calls, 0)
        self.assertFalse(append_called["value"])


if __name__ == "__main__":
    unittest.main()
