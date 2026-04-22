"""
word_count_bar.py
=================
Per-tab status bar showing live word count, character count, and estimated
reading time for the Markdown Reader application.

Integration points (in app.py / the editor module):
  1. Import: from word_count_bar import WordCountBar
  2. When creating a new editor tab, call:
         bar = WordCountBar(tab_frame)
         bar.pack(side="bottom", fill="x")
         bar.attach(text_widget)
  3. When switching tabs, call:
         bar.refresh()
  4. No teardown needed — bar.attach() manages its own bindings.

Dependencies: tkinter (stdlib), ttkbootstrap (already in requirements.txt)
"""

import re
import tkinter as tk
import ttkbootstrap as ttk

# Average silent reading speed (words per minute) used by many editors.
_WPM = 238

# Delay (ms) after the last keystroke before recomputing stats.
# Keeps the UI responsive on large documents.
_DEBOUNCE_MS = 400


def _strip_markdown(text: str) -> str:
    """
    Remove common Markdown syntax tokens so that word count reflects
    readable prose rather than raw markup characters.

    Handles: ATX headings, setext headings, bold/italic markers, inline code,
    fenced code blocks, blockquote markers, link/image syntax, HTML tags,
    horizontal rules, and table pipe characters.
    """
    # Fenced code blocks  (``` ... ``` or ~~~ ... ~~~)
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"~~~[\s\S]*?~~~", " ", text)

    # Inline code
    text = re.sub(r"`[^`]*`", " ", text)

    # HTML tags
    text = re.sub(r"<[^>]+>", " ", text)

    # Images  ![alt](url)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)

    # Links  [text](url)  — keep the link text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)

    # Reference-style links  [text][ref]
    text = re.sub(r"\[([^\]]*)\]\[[^\]]*\]", r"\1", text)

    # ATX headings  (# Heading)
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)

    # Bold / italic  (**text**, __text__, *text*, _text_)
    text = re.sub(r"\*{1,3}|_{1,3}", "", text)

    # Strikethrough  ~~text~~
    text = re.sub(r"~~", "", text)

    # Blockquote markers
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)

    # Horizontal rules
    text = re.sub(r"^[-*_]{3,}\s*$", "", text, flags=re.MULTILINE)

    # Table pipe characters
    text = re.sub(r"\|", " ", text)

    # Unordered list markers at line start
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)

    # Ordered list markers
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)

    return text


def _count_words(text: str) -> int:
    """
    Count words in *stripped* text.

    Uses Unicode-aware splitting so that CJK characters (each of which is
    semantically one word) are counted individually, while ASCII/Latin words
    are split on whitespace boundaries.
    """
    if not text.strip():
        return 0

    # CJK Unified Ideographs and common CJK extensions
    cjk_pattern = re.compile(
        r"[\u4e00-\u9fff"        # CJK Unified Ideographs
        r"\u3400-\u4dbf"         # CJK Extension A
        r"\U00020000-\U0002a6df" # CJK Extension B
        r"\u3040-\u309f"         # Hiragana
        r"\u30a0-\u30ff"         # Katakana
        r"\uac00-\ud7af]"        # Hangul Syllables
    )

    # Replace each CJK character with a whitespace-delimited token so that
    # str.split() picks them up as individual words.
    spaced = cjk_pattern.sub(r" \g<0> ", text)
    return len(spaced.split())


def _reading_time(word_count: int) -> str:
    """Return a human-readable estimated reading time string."""
    if word_count == 0:
        return "< 1 min read"
    minutes = word_count / _WPM
    if minutes < 1:
        return "< 1 min read"
    minutes = round(minutes)
    return f"{minutes} min read"


class WordCountBar(ttk.Frame):
    """
    A slim status bar widget that lives at the bottom of an editor tab.

    Displays:
      • Word count (Markdown-stripped)
      • Character count with spaces
      • Character count without spaces
      • Estimated reading time

    When the user has an active selection, the bar additionally shows the
    word and character counts of the selected region.

    Usage::

        bar = WordCountBar(parent_frame, bootstyle="secondary")
        bar.pack(side="bottom", fill="x")
        bar.attach(text_widget)   # call after the Text widget is created
    """

    def __init__(self, master, bootstyle: str = "secondary", **kwargs):
        super().__init__(master, **kwargs)

        self._text_widget: tk.Text | None = None
        self._debounce_id: str | None = None

        # ── layout ──────────────────────────────────────────────────────────
        # Single label on the left for all stats; padding keeps it away from
        # the window edge and matches the ttkbootstrap aesthetic.
        self._stats_var = tk.StringVar(value="")
        self._stats_label = ttk.Label(
            self,
            textvariable=self._stats_var,
            bootstyle=f"{bootstyle}-inverse",
            font=("", 10),
            padding=(8, 2),
            anchor="w",
        )
        self._stats_label.pack(side="left", fill="x", expand=True)

    # ── public API ───────────────────────────────────────────────────────────

    def attach(self, text_widget: tk.Text) -> None:
        """
        Bind this bar to *text_widget*.

        Safe to call multiple times — old bindings are cleaned up first.
        """
        self._detach()
        self._text_widget = text_widget

        # KeyRelease fires after the text widget has been updated, which is
        # exactly when we want to schedule a recount.
        text_widget.bind("<KeyRelease>", self._on_change, add="+")

        # <<Selection>> fires when the selection changes (mouse drag, Shift+arrow, etc.)
        text_widget.bind("<<Selection>>", self._on_change, add="+")

        # Immediate update when first attached (e.g., file just loaded).
        self.refresh()

    def refresh(self) -> None:
        """Force an immediate statistics refresh (e.g., on tab switch)."""
        self._cancel_debounce()
        self._update_stats()

    # ── private helpers ──────────────────────────────────────────────────────

    def _detach(self) -> None:
        """Remove bindings from the previously attached widget, if any."""
        if self._text_widget is not None:
            try:
                self._text_widget.unbind("<KeyRelease>")
                self._text_widget.unbind("<<Selection>>")
            except tk.TclError:
                pass  # widget may have been destroyed already
        self._text_widget = None
        self._cancel_debounce()

    def _on_change(self, _event=None) -> None:
        """Schedule a debounced statistics update."""
        self._cancel_debounce()
        self._debounce_id = self.after(_DEBOUNCE_MS, self._update_stats)

    def _cancel_debounce(self) -> None:
        if self._debounce_id is not None:
            self.after_cancel(self._debounce_id)
            self._debounce_id = None

    def _update_stats(self) -> None:
        """Recompute all statistics and update the label."""
        if self._text_widget is None:
            self._stats_var.set("")
            return

        # tk.Text always appends a trailing newline; strip it.
        full_text: str = self._text_widget.get("1.0", "end-1c")

        stripped = _strip_markdown(full_text)
        word_count = _count_words(stripped)
        char_with = len(full_text)
        char_without = len(full_text.replace(" ", "").replace("\n", "").replace("\t", ""))
        reading = _reading_time(word_count)

        parts = [
            f"{word_count:,} words",
            f"{char_with:,} chars",
            f"{char_without:,} chars (no spaces)",
            reading,
        ]

        # ── selection stats ──────────────────────────────────────────────────
        sel_info = self._selection_stats()
        if sel_info:
            parts.append(f"│ Selection: {sel_info}")

        self._stats_var.set("  ".join(parts))

    def _selection_stats(self) -> str | None:
        """
        Return a formatted selection-count string, or None if no selection.
        """
        w = self._text_widget
        try:
            sel_start = w.index("sel.first")
            sel_end = w.index("sel.last")
        except tk.TclError:
            return None  # no selection

        sel_text = w.get(sel_start, sel_end)
        if not sel_text:
            return None

        sel_stripped = _strip_markdown(sel_text)
        sel_words = _count_words(sel_stripped)
        sel_chars = len(sel_text)
        return f"{sel_words:,} words, {sel_chars:,} chars"