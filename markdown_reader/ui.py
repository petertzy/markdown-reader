import os
import re
import subprocess
import sys
import threading
from datetime import datetime, timezone
import tkinter as tk
import tkinter.font  # moved here from inside methods
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter.scrolledtext import ScrolledText

import markdown
import ttkbootstrap as ttkb
from ttkbootstrap import dialogs
from ttkbootstrap.constants import *
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from markdown_reader.file_handler import drop_file, load_file
from markdown_reader.logic import (
    APP_SETTINGS_FILE_PATH,
    AI_PROVIDER_DEFAULT_MODELS,
    AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES,
    TranslationConfigError,
    append_ai_automation_log,
    convert_html_to_markdown,
    convert_pdf_to_markdown,
    convert_pdf_to_markdown_docling,
    delete_secure_ai_api_key,
    export_to_docx,
    export_to_html,
    export_to_pdf,
    fetch_available_models,
    get_ai_automation_task_templates,
    get_ai_provider_display_name,
    get_ai_provider_env_var,
    get_ai_provider_model,
    get_secure_ai_api_key,
    is_secure_key_storage_available,
    load_ai_chat_histories,
    load_persisted_ai_settings,
    open_preview_in_browser,
    request_ai_agent_response,
    save_ai_chat_histories,
    load_ai_automation_logs,
    set_current_ai_provider,
    set_ai_provider_model,
    set_secure_ai_api_key,
    split_markdown_for_translation,
    translate_markdown_with_ai,
    update_preview,
)
from markdown_reader.utils import get_preview_file

from .plugins.pdf_exporter import export_markdown_to_pdf


class FileChangeHandler(FileSystemEventHandler):
    """
    The class that handles changes to files.

    :param FileSystemEventHandler: The file system event handler from the watchdog.events library.
    """

    def __init__(self, app, filepath):
        """
        :param MarkdownReader app: The instance of the MarkdownReader application.
        :param string filepath: The file path for the file to be monitored.
        """

        self.app = app
        self.filepath = os.path.abspath(filepath)

    def on_modified(self, event):
        """
        When the file is modified, reload the file after 100ms.

        :param event event: The file modification event.
        """

        if os.path.abspath(event.src_path) == self.filepath:
            self.app.root.after(100, lambda: self.app.load_file(self.filepath))


class HoverTooltip:
    """Simple hover tooltip for Tk/ttk widgets."""

    def __init__(self, widget, text, delay=450, max_width=280):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.max_width = max_width
        self._after_id = None
        self._tooltip_window = None
        self._bind_events()

    def _bind_events(self):
        self.widget.bind("<Enter>", self._schedule, add="+")
        self.widget.bind("<Leave>", self._hide, add="+")
        self.widget.bind("<ButtonPress>", self._hide, add="+")
        self.widget.bind("<FocusOut>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._cancel_scheduled()
        self._after_id = self.widget.after(self.delay, self._show)

    def _cancel_scheduled(self):
        if self._after_id is not None:
            self.widget.after_cancel(self._after_id)
            self._after_id = None

    def _show(self):
        self._after_id = None
        if self._tooltip_window is not None or not self.text:
            return

        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 8

        self._tooltip_window = tk.Toplevel(self.widget)
        self._tooltip_window.wm_overrideredirect(True)
        self._tooltip_window.wm_attributes("-topmost", True)

        outer = tk.Frame(
            self._tooltip_window,
            bg="#d8dee8",
            borderwidth=1,
            relief="solid",
        )
        outer.pack()

        label = tk.Label(
            outer,
            text=self.text,
            justify="left",
            anchor="w",
            wraplength=self.max_width,
            padx=10,
            pady=6,
            bg="#ffffff",
            fg="#1f2937",
            font=("TkDefaultFont", 10),
        )
        label.pack()

        self._tooltip_window.update_idletasks()
        tip_width = self._tooltip_window.winfo_width()
        tip_height = self._tooltip_window.winfo_height()
        screen_w = self._tooltip_window.winfo_screenwidth()
        screen_h = self._tooltip_window.winfo_screenheight()

        if x + tip_width > screen_w - 10:
            x = max(10, screen_w - tip_width - 10)
        if y + tip_height > screen_h - 10:
            y = self.widget.winfo_rooty() - tip_height - 8
        y = max(10, y)

        self._tooltip_window.geometry(f"+{x}+{y}")

    def _hide(self, _event=None):
        self._cancel_scheduled()
        if self._tooltip_window is not None:
            self._tooltip_window.destroy()
            self._tooltip_window = None


class MarkdownReader:
    """
    The class that creates the instance of the Markdown reader application.
    """

    def __init__(self, root):
        """
        :param tk.Tk root: The window that the application uses as a display.
        """

        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("1280x795")

        # Enable window resizing - force both width and height to be resizable
        self.root.resizable(width=True, height=True)
        # Set minimum window size to prevent it from being too small
        self.root.minsize(800, 600)

        # Ensure persisted AI settings are available before initializing UI state.
        load_persisted_ai_settings()

        self.dark_mode = False
        self.preview_file = get_preview_file()
        self.current_file_path = None
        self.observer = None

        # --- Toolbar state ---
        self.current_font_family = "Consolas"
        self.current_font_size = 14
        self.current_fg_color = "#000000"
        self.current_bg_color = "#ffffff"

        # Flag to prevent marking as modified during file loading
        self._loading_file = False

        # Track which tabs have unsaved modifications
        self.modified_tabs = set()

        # PDF conversion mode: False = PyMuPDF (fast), True = Docling (advanced)
        self.use_docling_pdf = False

        # IME state tracking per widget
        self._ime_states = {}
        self._tooltips = []

        # Translation defaults
        self.translation_source_language = "English"
        self.translation_target_language = "German"
        self.translation_languages = [
            "English",
            "Japanese",
            "Korean",
            "German",
            "French",
            "Spanish",
            "Italian",
            "Portuguese",
            "Russian",
            "Arabic",
            "Hindi",
            "Dutch",
            "Swedish",
            "Polish",
            "Turkish",
            "Vietnamese",
            "Thai",
            "Indonesian",
            "Chinese (Simplified)",
            "Chinese (Traditional)",
        ]
        self.ai_provider_var = tk.StringVar(
            value=os.getenv("AI_PROVIDER", "openrouter").strip().lower() or "openrouter"
        )
        self.ai_chat_panel_visible_var = tk.BooleanVar(value=False)
        self.ai_chat_context_mode_var = tk.StringVar(value="selection")
        self.translation_progress_var = tk.DoubleVar(value=0)
        self.translation_status_var = tk.StringVar(value="")
        self.translation_job_active = False
        self.ai_agent_status_var = tk.StringVar(value="")
        self.ai_chat_histories = load_ai_chat_histories()
        self.ai_chat_pending_actions = {}
        self.ai_automation_templates = get_ai_automation_task_templates()
        self.ai_action_audit_logs = load_ai_automation_logs()
        self.ai_last_applied_action_id_by_doc = {}
        self._chat_busy = False
        self._untitled_counter = 0
        self.tab_document_ids = []
        self._translation_session_counter = 0
        self._translation_cancel_requested = False
        self._last_search_query = ""
        self._search_dialog = None
        self._search_entry = None
        self._replace_entry = None
        self._search_status_var = tk.StringVar(value="")
        self._last_replace_text = ""
        self._search_case_sensitive_var = tk.BooleanVar(value=False)
        self._search_whole_word_var = tk.BooleanVar(value=False)
        self._search_regex_var = tk.BooleanVar(value=False)

        self.global_shortcuts = [
            ("New File", "<Control-KeyPress-n>", self.new_file),
            ("Open File", "<Control-KeyPress-o>", self.open_file),
            ("Save File", "<Control-KeyPress-s>", self.save_file),
            ("Close Current Tab", "<Control-KeyPress-w>", self.close_current_tab),
            ("Close All Tabs", "<Control-Shift-KeyPress-W>", self.close_all_tabs),
            ("Undo", "<Control-KeyPress-z>", self.undo_action),
            ("Redo", "<Control-KeyPress-y>", self.redo_action),
            ("Redo", "<Control-Shift-KeyPress-Z>", self.redo_action),
            ("Toggle AI Agent Panel", "<Control-Shift-KeyPress-A>", self._toggle_ai_chat_panel_shortcut),
            (
                "Translate Full Document with AI",
                "<Control-Shift-KeyPress-T>",
                lambda: self.translate_with_ai(selected_only=False),
            ),
            (
                "Open Preview in Browser",
                "<Control-Shift-KeyPress-O>",
                lambda: open_preview_in_browser(self.preview_file, self),
            ),
            ("Toggle Dark Mode", "<F6>", self.toggle_dark_mode),
        ]
        self.editor_shortcuts = [
            ("Search", "<Control-KeyPress-f>", self.open_search_dialog),
            ("Replace", "<Control-KeyPress-h>", self.open_replace_dialog),
            ("Bold", "<Control-KeyPress-b>", self.toggle_bold),
            ("Italic", "<Control-KeyPress-i>", self.toggle_italic),
            ("Underline", "<Control-KeyPress-u>", self.toggle_underline),
            (
                "Translate Selected Text with AI",
                "<Control-KeyPress-t>",
                lambda: self.translate_with_ai(selected_only=True),
            ),
            ("Heading 1", "<Control-KeyPress-1>", lambda: self.apply_style("Heading 1")),
            ("Heading 2", "<Control-KeyPress-2>", lambda: self.apply_style("Heading 2")),
            ("Heading 3", "<Control-KeyPress-3>", lambda: self.apply_style("Heading 3")),
            ("Normal Text", "<Control-KeyPress-0>", lambda: self.apply_style("Normal text")),
            ("Insert Table", "<Control-Alt-KeyPress-t>", self.insert_table),
            ("Export to HTML", "<Control-Alt-KeyPress-h>", self.export_to_html_dialog),
            ("Export to Word", "<Control-Alt-KeyPress-d>", self.export_to_docx_dialog),
            ("Export to PDF", "<Control-Alt-KeyPress-p>", self.export_to_pdf_dialog),
        ]

        if sys.platform == "darwin":
            self.global_shortcuts.extend(
                [
                    ("New File", "<Command-KeyPress-n>", self.new_file),
                    ("Open File", "<Command-KeyPress-o>", self.open_file),
                    ("Save File", "<Command-KeyPress-s>", self.save_file),
                    ("Close Current Tab", "<Command-KeyPress-w>", self.close_current_tab),
                    ("Close All Tabs", "<Command-Shift-KeyPress-W>", self.close_all_tabs),
                    ("Undo", "<Command-KeyPress-z>", self.undo_action),
                    ("Redo", "<Command-Shift-KeyPress-Z>", self.redo_action),
                    ("Toggle AI Agent Panel", "<Command-Shift-KeyPress-A>", self._toggle_ai_chat_panel_shortcut),
                    (
                        "Translate Full Document with AI",
                        "<Command-Shift-KeyPress-T>",
                        lambda: self.translate_with_ai(selected_only=False),
                    ),
                    (
                        "Open Preview in Browser",
                        "<Command-Shift-KeyPress-O>",
                        lambda: open_preview_in_browser(self.preview_file, self),
                    ),
                ]
            )
            self.editor_shortcuts.extend(
                [
                    ("Search", "<Command-KeyPress-f>", self.open_search_dialog),
                    ("Replace", "<Command-Option-KeyPress-f>", self.open_replace_dialog),
                    ("Bold", "<Command-KeyPress-b>", self.toggle_bold),
                    ("Italic", "<Command-KeyPress-i>", self.toggle_italic),
                    ("Underline", "<Command-KeyPress-u>", self.toggle_underline),
                    (
                        "Translate Selected Text with AI",
                        "<Command-KeyPress-t>",
                        lambda: self.translate_with_ai(selected_only=True),
                    ),
                    ("Heading 1", "<Command-KeyPress-1>", lambda: self.apply_style("Heading 1")),
                    ("Heading 2", "<Command-KeyPress-2>", lambda: self.apply_style("Heading 2")),
                    ("Heading 3", "<Command-KeyPress-3>", lambda: self.apply_style("Heading 3")),
                    ("Normal Text", "<Command-KeyPress-0>", lambda: self.apply_style("Normal text")),
                    ("Insert Table", "<Command-Option-KeyPress-t>", self.insert_table),
                    ("Export to HTML", "<Command-Option-KeyPress-h>", self.export_to_html_dialog),
                    ("Export to Word", "<Command-Option-KeyPress-d>", self.export_to_docx_dialog),
                    ("Export to PDF", "<Command-Option-KeyPress-p>", self.export_to_pdf_dialog),
                ]
            )

        self.root.protocol("WM_DELETE_WINDOW", self.quit)

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        """
        Sets up the various menus, toolbar, and fonts.
        """

        style = ttkb.Style()
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_file)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_command(label="Save File", command=self.save_file)
        filemenu.add_separator()
        filemenu.add_command(label="Export to HTML", command=self.export_to_html_dialog)
        filemenu.add_command(label="Export to Word", command=self.export_to_docx_dialog)
        filemenu.add_command(label="Export to PDF", command=self.export_to_pdf_dialog)
        filemenu.add_separator()
        filemenu.add_command(label="Close", command=self.close_current_tab)
        filemenu.add_command(label="Close All", command=self.close_all_tabs)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewmenu.add_command(
            label="Open Preview in Browser",
            command=lambda: open_preview_in_browser(self.preview_file, self),
        )
        viewmenu.add_separator()
        viewmenu.add_checkbutton(
            label="Show AI Agent Panel",
            variable=self.ai_chat_panel_visible_var,
            command=self.toggle_ai_chat_panel,
        )
        menubar.add_cascade(label="View", menu=viewmenu)

        editmenu = ttkb.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Undo", command=self.undo_action)
        editmenu.add_command(label="Redo", command=self.redo_action)
        editmenu.add_separator()
        editmenu.add_command(label="Search...", command=self.open_search_dialog)
        editmenu.add_command(label="Replace...", command=self.open_replace_dialog)
        editmenu.add_separator()
        translatemenu = tk.Menu(editmenu, tearoff=0)
        translatemenu.add_command(
            label="Translate Selected Text with AI",
            command=lambda: self.translate_with_ai(selected_only=True),
        )
        translatemenu.add_command(
            label="Translate Full Document with AI",
            command=lambda: self.translate_with_ai(selected_only=False),
        )
        editmenu.add_cascade(label="Translate with AI", menu=translatemenu)
        menubar.add_cascade(label="Edit", menu=editmenu)

        settingsmenu = tk.Menu(menubar, tearoff=0)
        settingsmenu.add_command(
            label="AI Provider & API Keys...",
            command=self.open_ai_provider_config,
        )
        settingsmenu.add_separator()
        settingsmenu.add_command(
            label="Open AI Data Folder",
            command=self.open_ai_data_folder,
        )
        menubar.add_cascade(label="Settings", menu=settingsmenu)

        # Tools menu with PDF conversion options
        toolsmenu = tk.Menu(menubar, tearoff=0)
        self.pdf_mode_var = tk.BooleanVar(value=self.use_docling_pdf)
        toolsmenu.add_checkbutton(
            label="Use Advanced PDF Conversion (Docling)",
            variable=self.pdf_mode_var,
            command=self.toggle_pdf_mode,
        )
        toolsmenu.add_separator()
        toolsmenu.add_command(
            label="PDF Converter Info", command=self.show_pdf_converter_info
        )
        menubar.add_cascade(label="Tools", menu=toolsmenu)

        # ADD THIS NEW BLOCK:
        tablemenu = tk.Menu(menubar, tearoff=0)
        tablemenu.add_command(label="Insert Table...", command=self.insert_table)
        tablemenu.add_separator()
        tablemenu.add_command(label="Table Syntax Help", command=self.show_table_help)
        menubar.add_cascade(label="Table", menu=tablemenu)

        shortcutsmenu = tk.Menu(menubar, tearoff=0)
        for action_name, pattern, handler in self.global_shortcuts:
            shortcutsmenu.add_command(
                label=action_name,
                accelerator=self._format_shortcut_pattern(pattern),
                command=handler,
            )
        shortcutsmenu.add_separator()
        for action_name, pattern, handler in self.editor_shortcuts:
            shortcutsmenu.add_command(
                label=action_name,
                accelerator=self._format_shortcut_pattern(pattern),
                command=handler,
            )
        menubar.add_cascade(label="Shortcuts", menu=shortcutsmenu)

        helpmenu = tk.Menu(menubar, tearoff=0)
        helpmenu.add_command(label="Help Contents", command=self.show_help)
        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

        # --- Toolbar ---
        style.configure("primary.TFrame")
        toolbar = ttkb.Frame(
            self.root, relief=tk.RAISED, style="primary.TFrame", padding=(5, 5, 0, 5)
        )
        # Style dropdown
        self.style_var = tk.StringVar(value="Normal text")
        style_options = ["Normal text", "Heading 1", "Heading 2", "Heading 3"]
        style.configure("info.Outline.TMenubutton")
        # style_menu = tk.OptionMenu(toolbar, self.style_var, *style_options, command=self.apply_style)
        style_menu = ttkb.Menubutton(
            toolbar, textvariable=self.style_var, style="info.Outline.TMenubutton"
        )
        style_menu.config(width=12)
        style_menu.pack(side=tk.LEFT, padx=2, pady=2)
        self._tooltips.append(HoverTooltip(style_menu, "Text style (Normal, Heading 1-3)"))
        menu_ = tk.Menu(style_menu, tearoff=0)
        for s in style_options:
            menu_.add_radiobutton(
                label=s,
                variable=self.style_var,
                command=lambda s=s: self.apply_style(s),
            )
        style_menu["menu"] = menu_
        # Font family dropdown
        fonts = sorted(set(tkinter.font.families()))
        self.font_var = ttkb.StringVar(value="Consolas")
        font_menu = ttkb.Menubutton(
            toolbar, textvariable=self.font_var, style="info.Outline.TMenubutton"
        )

        font_menu.config(width=10)
        font_menu.pack(side=tk.LEFT, padx=2)
        self._tooltips.append(HoverTooltip(font_menu, "Font family"))

        menu = tk.Menu(font_menu, tearoff=0)
        for f in fonts[:20]:
            menu.add_radiobutton(
                label=f, variable=self.font_var, command=lambda f=f: self.apply_font(f)
            )
        font_menu["menu"] = menu
        # Font size
        self.font_size_var = tk.IntVar(value=14)
        button_width = 3
        uniform_padding = (5, 4)
        # entry config
        style.configure("info.TEntry")
        decrease_size_btn = ttkb.Button(
            toolbar,
            text="-",
            bootstyle=(DANGER, OUTLINE),
            width=button_width,
            padding=uniform_padding,
            command=lambda: self.change_font_size(-1),
        )
        decrease_size_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(decrease_size_btn, "Decrease font size"))

        font_size_entry = ttkb.Entry(
            toolbar,
            textvariable=self.font_size_var,
            width=3,
            style="info.TEntry",
            justify="center",
        )
        font_size_entry.pack(side=tk.LEFT)
        self._tooltips.append(HoverTooltip(font_size_entry, "Font size"))

        increase_size_btn = ttkb.Button(
            toolbar,
            text="+",
            bootstyle=(SUCCESS, OUTLINE),
            width=button_width,
            padding=uniform_padding,
            command=lambda: self.change_font_size(1),
        )
        increase_size_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(increase_size_btn, "Increase font size"))

        # font configuration

        # toggle bold
        style.configure(
            "bold.info.TButton", font=("Arial", 9, "bold"), padding=uniform_padding
        )
        # toggle italic
        style.configure(
            "italic.info.TButton", font=("Arial", 9, "italic"), padding=uniform_padding
        )
        # toggle underline
        style.configure(
            "underline.info.TButton",
            font=("Arial", 9, "underline"),
            padding=uniform_padding,
        )
        # insert table
        style.configure(
            "insert.info.TButton", font=("Arial", 9), padding=uniform_padding
        )
        # choose fg color
        style.configure("fg.info.TButton", font=("Arial", 9), padding=uniform_padding)
        # highlight
        style.configure("bg.info.TButton", font=("Arial", 9), padding=uniform_padding)

        bold_btn = ttkb.Button(
            toolbar,
            text="B",
            style="bold.info.TButton",
            width=button_width,
            command=self.toggle_bold,
        )
        bold_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(bold_btn, "Toggle bold"))

        italic_btn = ttkb.Button(
            toolbar,
            text="I",
            style="italic.info.TButton",
            width=button_width,
            command=self.toggle_italic,
        )
        italic_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(italic_btn, "Toggle italic"))

        underline_btn = ttkb.Button(
            toolbar,
            text="U",
            style="underline.info.TButton",
            width=button_width,
            command=self.toggle_underline,
        )
        underline_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(underline_btn, "Toggle underline"))

        insert_table_btn = ttkb.Button(
            toolbar,
            text="⊞",
            style="insert.info.TButton",
            width=button_width,
            command=self.insert_table,
        )
        insert_table_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(insert_table_btn, "Insert table"))
        # Text color
        text_color_btn = ttkb.Button(
            toolbar,
            text="A",
            style="fg.info.TButton",
            width=button_width,
            command=self.choose_fg_color,
        )
        text_color_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(text_color_btn, "Text color"))
        # Highlight color
        highlight_color_btn = ttkb.Button(
            toolbar,
            text="\u0332",
            style="bg.info.TButton",
            width=button_width,
            command=self.choose_bg_color,
        )
        highlight_color_btn.pack(side=tk.LEFT, padx=5)
        self._tooltips.append(HoverTooltip(highlight_color_btn, "Highlight color"))
        toolbar.pack(fill=tk.X)

        self.translation_progress_frame = ttkb.Frame(self.root, padding=(10, 6))
        self.translation_progress_label = ttk.Label(
            self.translation_progress_frame,
            textvariable=self.translation_status_var,
        )
        self.translation_progress_label.pack(side=tk.TOP, anchor="w")
        _prog_row = ttkb.Frame(self.translation_progress_frame)
        _prog_row.pack(fill=tk.X, expand=True, pady=(4, 0))
        self.translation_progress = ttk.Progressbar(
            _prog_row,
            orient=tk.HORIZONTAL,
            mode="determinate",
            variable=self.translation_progress_var,
        )
        self.translation_progress.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._translation_cancel_btn = ttkb.Button(
            _prog_row,
            text="Cancel",
            bootstyle="danger-outline",
            command=self._request_translation_cancel,
            width=8,
        )
        self._translation_cancel_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.editor_split_pane = ttk.Panedwindow(self.root, orient=tk.HORIZONTAL)
        self.editor_split_pane.pack(fill=tk.BOTH, expand=True)

        self.editor_panel = ttkb.Frame(self.editor_split_pane)
        self.notebook = ttk.Notebook(self.editor_panel)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        self.editor_split_pane.add(self.editor_panel, weight=4)

        self.ai_chat_panel = ttkb.Frame(self.editor_split_pane, padding=(8, 8, 8, 8))
        self._build_ai_chat_panel()
        self.editor_split_pane.add(self.ai_chat_panel, weight=2)

        self.editors = []
        self.file_paths = []

        # Create context menu for tabs
        self.tab_context_menu = tk.Menu(self.root, tearoff=0)
        self.tab_context_menu.add_command(
            label="Close", command=self.close_tab_from_context_menu
        )

        # Bind right-click for context menu
        self.notebook.bind(
            "<Button-2>"
            if self.root.tk.call("tk", "windowingsystem") == "aqua"
            else "<Button-3>",
            self.show_tab_context_menu,
        )
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed)

        self._set_ai_chat_panel_visible(self.ai_chat_panel_visible_var.get())

        self.new_file()

    def bind_events(self):
        """
        Register application-wide keyboard shortcuts.

        :return: A None value after all app-wide shortcut bindings are registered.

        :raises tk.TclError: If a shortcut binding cannot be registered on the root widget.
        """

        for _shortcut_name, pattern, handler in self.global_shortcuts:
            self.root.bind_all(
                pattern,
                lambda event, handler=handler: (handler(), "break")[1],
            )

    def _build_ai_chat_panel(self):
        """Create the dockable AI agent chat panel widgets."""

        header = ttkb.Frame(self.ai_chat_panel)
        header.pack(fill=tk.X, pady=(0, 3))

        ttk.Label(
            header,
            text="AI Agent",
            font=("TkDefaultFont", 11, "bold"),
        ).pack(side=tk.LEFT)
        ttkb.Button(
            header,
            text="Hide",
            width=8,
            bootstyle="secondary-outline",
            command=lambda: self.ai_chat_panel_visible_var.set(False) or self.toggle_ai_chat_panel(),
        ).pack(side=tk.RIGHT)

        self.ai_chat_history_box = ScrolledText(
            self.ai_chat_panel,
            wrap=tk.WORD,
            height=12,
            state=tk.DISABLED,
            font=(self.current_font_family, max(11, self.current_font_size - 1)),
        )
        self.ai_chat_history_box.pack(fill=tk.BOTH, expand=True)

        controls = ttkb.Frame(self.ai_chat_panel)
        controls.pack(fill=tk.X, pady=(4, 3))

        ttkb.Button(
            controls,
            text="Format Section",
            bootstyle="info-outline",
            command=lambda: self._send_ai_agent_preset("format this section"),
            width=12,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttkb.Button(
            controls,
            text="Generate TOC",
            bootstyle="warning-outline",
            command=lambda: self._send_ai_agent_preset("generate table of contents"),
            width=12,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttkb.Button(
            controls,
            text="Generate Summary",
            bootstyle="primary-outline",
            command=lambda: self._send_ai_agent_preset("generate summary"),
            width=15,
        ).pack(side=tk.LEFT, padx=(0, 6))
        ttkb.Button(
            controls,
            text="Clear History",
            bootstyle="danger-outline",
            command=self._clear_current_chat_history,
            width=12,
        ).pack(side=tk.LEFT)

        template_row = ttkb.Frame(self.ai_chat_panel)
        template_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(template_row, text="Automation Template:").pack(side=tk.LEFT, padx=(0, 8))
        self.ai_template_var = tk.StringVar(value=(self.ai_automation_templates[0]["id"] if self.ai_automation_templates else ""))
        template_choices = [f"{item['id']}: {item['title']}" for item in self.ai_automation_templates]
        self._ai_template_combo = ttk.Combobox(
            template_row,
            state="readonly",
            width=44,
            values=template_choices,
        )
        if template_choices:
            self._ai_template_combo.current(0)
        self._ai_template_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 6))
        ttkb.Button(
            template_row,
            text="Run Template",
            bootstyle="secondary-outline",
            width=12,
            command=self._run_selected_ai_template,
        ).pack(side=tk.LEFT)

        context_scope_row = ttkb.Frame(self.ai_chat_panel)
        context_scope_row.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(context_scope_row, text="Context Scope:").pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            context_scope_row,
            text="Full document",
            variable=self.ai_chat_context_mode_var,
            value="full",
        ).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Radiobutton(
            context_scope_row,
            text="Selection only",
            variable=self.ai_chat_context_mode_var,
            value="selection",
        ).pack(side=tk.LEFT)

        self.ai_chat_input_box = ScrolledText(
            self.ai_chat_panel,
            wrap=tk.WORD,
            height=3,
            font=(self.current_font_family, max(11, self.current_font_size - 1)),
        )
        self.ai_chat_input_box.pack(fill=tk.X)
        self.ai_chat_input_box.bind(
            "<Control-Return>",
            lambda _event: (self.send_ai_agent_message(), "break")[1],
        )
        self.ai_chat_input_box.bind(
            "<Command-Return>",
            lambda _event: (self.send_ai_agent_message(), "break")[1],
        )

        footer = ttkb.Frame(self.ai_chat_panel)
        footer.pack(fill=tk.X, pady=(3, 0))

        self._ai_apply_btn = ttkb.Button(
            footer,
            text="Apply Suggestion",
            bootstyle="success-outline",
            command=self.apply_ai_agent_action,
            state=tk.DISABLED,
            width=14,
        )
        self._ai_apply_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._ai_reject_btn = ttkb.Button(
            footer,
            text="Reject",
            bootstyle="danger-outline",
            command=self.reject_ai_agent_action,
            state=tk.DISABLED,
            width=10,
        )
        self._ai_reject_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._ai_undo_btn = ttkb.Button(
            footer,
            text="Undo AI Task",
            bootstyle="warning-outline",
            command=self.undo_last_ai_action,
            width=12,
        )
        self._ai_undo_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._ai_logs_btn = ttkb.Button(
            footer,
            text="Audit Log",
            bootstyle="secondary-outline",
            command=self.show_ai_automation_log,
            width=10,
        )
        self._ai_logs_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._ai_send_btn = ttkb.Button(
            footer,
            text="Send",
            bootstyle="success",
            command=self.send_ai_agent_message,
            width=8,
        )
        self._ai_send_btn.pack(side=tk.LEFT)

        ttk.Label(
            footer,
            textvariable=self.ai_agent_status_var,
            foreground="gray",
            anchor="e",
        ).pack(side=tk.RIGHT, fill=tk.X, expand=True)

    def _set_ai_chat_panel_visible(self, visible):
        """Show or hide the AI chat panel in the split pane."""

        should_show = bool(visible)
        panes = {str(pane) for pane in self.editor_split_pane.panes()}
        panel_widget = str(self.ai_chat_panel)
        if should_show and panel_widget not in panes:
            self.editor_split_pane.add(self.ai_chat_panel, weight=2)
        if not should_show and panel_widget in panes:
            self.editor_split_pane.forget(self.ai_chat_panel)

    def toggle_ai_chat_panel(self):
        """Toggle the dockable AI chat panel."""

        self._set_ai_chat_panel_visible(self.ai_chat_panel_visible_var.get())

    def _toggle_ai_chat_panel_shortcut(self):
        """Toggle AI panel from keyboard shortcut and sync menu check state."""

        self.ai_chat_panel_visible_var.set(not self.ai_chat_panel_visible_var.get())
        self.toggle_ai_chat_panel()

    def _get_document_id_for_tab(self, tab_index=None):
        """Return persistent document id for a tab."""

        if tab_index is None:
            if not self.editors:
                return None
            tab_index = self.notebook.index(self.notebook.select())

        if 0 <= tab_index < len(self.tab_document_ids):
            return self.tab_document_ids[tab_index]
        return None

    def _persist_ai_chat_histories(self):
        """Persist chat history data."""

        save_ai_chat_histories(self.ai_chat_histories)

    def _migrate_chat_document_key(self, old_doc_id, new_doc_id):
        """Migrate chat history and pending action to a new document id."""

        old_key = (old_doc_id or "").strip()
        new_key = (new_doc_id or "").strip()
        if not old_key or not new_key or old_key == new_key:
            return

        old_history = self.ai_chat_histories.pop(old_key, [])
        new_history = self.ai_chat_histories.get(new_key, [])
        combined = (new_history + old_history)[-80:]
        if combined:
            self.ai_chat_histories[new_key] = combined

        old_action = self.ai_chat_pending_actions.pop(old_key, None)
        if old_action:
            self.ai_chat_pending_actions[new_key] = old_action

        self._persist_ai_chat_histories()

    def _render_current_chat_history(self):
        """Render current tab chat history in the panel."""

        if not hasattr(self, "ai_chat_history_box"):
            return

        doc_id = self._get_document_id_for_tab()
        messages = self.ai_chat_histories.get(doc_id, []) if doc_id else []

        box = self.ai_chat_history_box
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        for item in messages:
            role = item.get("role", "assistant")
            prefix = "You" if role == "user" else "AI"
            content = (item.get("content") or "").strip()
            if content:
                box.insert(tk.END, f"{prefix}: {content}\n\n")
        box.configure(state=tk.DISABLED)
        box.see(tk.END)

        action = self.ai_chat_pending_actions.get(doc_id, {"type": "none"}) if doc_id else {"type": "none"}
        has_action = action.get("type") in ("replace_selection", "replace_document") and bool(
            str(action.get("content", "")).strip()
        )
        self._ai_apply_btn.configure(state=(tk.NORMAL if has_action else tk.DISABLED))
        self._ai_reject_btn.configure(state=(tk.NORMAL if has_action else tk.DISABLED))

    def _append_chat_message(self, role, content, tab_index=None):
        """Append a chat message to the history of the selected tab."""

        clean_role = (role or "assistant").strip().lower()
        clean_content = (content or "").strip()
        if clean_role not in ("user", "assistant") or not clean_content:
            return

        doc_id = self._get_document_id_for_tab(tab_index)
        if not doc_id:
            return

        bucket = self.ai_chat_histories.setdefault(doc_id, [])
        bucket.append({"role": clean_role, "content": clean_content})
        if len(bucket) > 80:
            del bucket[:-80]
        self._persist_ai_chat_histories()
        self._render_current_chat_history()

    def _append_ai_audit_log(
        self,
        status,
        action_type,
        user_message="",
        content="",
        reason="",
        related_action_id="",
        action_id="",
        doc_id=None,
    ):
        """Append and persist a single AI automation audit event."""

        clean_status = (status or "").strip().lower()
        clean_action_type = (action_type or "").strip().lower() or "none"
        preview = (content or "").strip()
        if len(preview) > 400:
            preview = preview[:400] + " ..."

        target_doc_id = (doc_id or self._get_document_id_for_tab() or "").strip()
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "doc_id": target_doc_id,
            "status": clean_status,
            "action_type": clean_action_type,
            "reason": (reason or "").strip(),
            "user_message": (user_message or "").strip(),
            "content_preview": preview,
            "related_action_id": (related_action_id or "").strip(),
            "action_id": (action_id or "").strip(),
        }
        self.ai_action_audit_logs.append(entry)
        if len(self.ai_action_audit_logs) > AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES:
            del self.ai_action_audit_logs[:-AI_AUTOMATION_MAX_AUDIT_LOG_ENTRIES]
        append_ai_automation_log(entry)

    def _run_selected_ai_template(self):
        """Send selected automation template prompt to the AI agent input."""

        if not hasattr(self, "_ai_template_combo"):
            return

        selected_label = (self._ai_template_combo.get() or "").strip()
        if not selected_label:
            dialogs.Messagebox.show_info("AI Agent", "Please select an automation template.")
            return

        template_id = selected_label.split(":", 1)[0].strip()
        selected_template = None
        for item in self.ai_automation_templates:
            if item.get("id") == template_id:
                selected_template = item
                break

        if not selected_template:
            dialogs.Messagebox.show_info("AI Agent", "Selected template is not available.")
            return

        requires_selection = bool(selected_template.get("requires_selection", False))
        if requires_selection:
            text_area = self.get_current_text_area()
            if text_area:
                try:
                    selected = text_area.get("sel.first", "sel.last")
                except tk.TclError:
                    selected = ""
                if not selected.strip():
                    dialogs.Messagebox.show_info(
                        "AI Agent",
                        "This template requires selected text in the editor.",
                    )
                    return

        prompt = str(selected_template.get("prompt", "")).strip()
        if not prompt:
            return
        self._send_ai_agent_preset(prompt)

    def show_ai_automation_log(self):
        """Show recent AI automation audit logs in a dialog."""

        display_limit = 10

        # Refresh from persisted store so the dialog always reflects latest data.
        persisted_logs = load_ai_automation_logs(limit=display_limit)
        if persisted_logs:
            self.ai_action_audit_logs = persisted_logs

        if not self.ai_action_audit_logs:
            dialogs.Messagebox.show_info("No AI automation actions logged yet.", "AI Audit Log")
            return

        rows = []
        for item in self.ai_action_audit_logs[-display_limit:]:
            stamp = str(item.get("timestamp", "")).strip()
            status = str(item.get("status", "")).strip() or "unknown"
            action_type = str(item.get("action_type", "")).strip() or "none"
            reason = str(item.get("reason", "")).strip()
            line = f"{stamp} | {status} | {action_type}"
            if reason:
                line += f" | {reason}"
            rows.append(line)

        text = "\n".join(rows)
        dialogs.Messagebox.show_info(text, "AI Audit Log")

    def _on_notebook_tab_changed(self, _event=None):
        """Refresh AI chat panel when switching tabs."""

        self.ai_agent_status_var.set("")
        self._render_current_chat_history()

    def _clear_current_chat_history(self):
        """Clear chat history for the current document."""

        doc_id = self._get_document_id_for_tab()
        if not doc_id:
            return
        if not messagebox.askyesno("Clear Chat", "Clear chat history for this document?"):
            return

        self.ai_chat_histories.pop(doc_id, None)
        self.ai_chat_pending_actions.pop(doc_id, None)
        self._persist_ai_chat_histories()
        self._render_current_chat_history()

    def _send_ai_agent_preset(self, command_text):
        """Send common preset commands to the AI agent."""

        cmd = (command_text or "").strip()
        if not cmd:
            return
        self.ai_chat_input_box.delete("1.0", tk.END)
        self.ai_chat_input_box.insert("1.0", cmd)
        self.send_ai_agent_message()

    def send_ai_agent_message(self):
        """Send a message to the AI agent with document context."""

        if self._chat_busy:
            dialogs.Messagebox.show_info("AI Agent", "AI Agent is processing another request.")
            return

        text_area = self.get_current_text_area()
        if not text_area:
            dialogs.Messagebox.show_info("No document", "Please open or create a document first.")
            return

        user_message = self.ai_chat_input_box.get("1.0", "end-1c").strip()
        if not user_message:
            return

        tab_index = self.notebook.index(self.notebook.select())
        doc_id = self._get_document_id_for_tab(tab_index)
        if not doc_id:
            return

        context_mode = (self.ai_chat_context_mode_var.get() or "full").strip().lower()
        if context_mode == "selection":
            document_text = ""
        else:
            document_text = text_area.get("1.0", "end-1c")
        try:
            selected_text = text_area.get("sel.first", "sel.last")
        except tk.TclError:
            selected_text = ""

        if context_mode == "selection" and not selected_text.strip():
            dialogs.Messagebox.show_info(
                "AI Agent",
                "Selection-only mode is enabled. Please select text first.",
            )
            return

        history_snapshot = list(self.ai_chat_histories.get(doc_id, []))
        self._append_chat_message("user", user_message, tab_index=tab_index)
        self.ai_chat_input_box.delete("1.0", tk.END)

        self._chat_busy = True
        self._ai_send_btn.configure(state=tk.DISABLED)
        self.ai_agent_status_var.set("AI Agent is thinking...")

        def worker():
            try:
                while True:
                    try:
                        result = request_ai_agent_response(
                            user_message,
                            document_text=document_text,
                            selected_text=selected_text,
                            chat_history=history_snapshot,
                        )
                        self.root.after(
                            0,
                            lambda data=result, idx=tab_index, msg=user_message: self._finish_ai_agent_response(data, idx, msg),
                        )
                        break
                    except TranslationConfigError as exc:
                        dialog_result = self._request_translation_api_key(exc)
                        if not dialog_result:
                            raise RuntimeError("No API key provided.") from exc
                        self._apply_ai_key_dialog_result(dialog_result, show_feedback=False)
            except Exception as exc:
                self.root.after(0, lambda err=str(exc): self._fail_ai_agent_response(err))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_ai_agent_response(self, result, tab_index, user_message=""):
        """Finalize a successful AI agent response."""

        self._chat_busy = False
        self._ai_send_btn.configure(state=tk.NORMAL)

        tab_doc_id = self._get_document_id_for_tab(tab_index)
        if not tab_doc_id:
            self.ai_agent_status_var.set("")
            return

        assistant_message = str((result or {}).get("assistant_message", "")).strip()

        action = (result or {}).get("proposed_action", {})
        if not isinstance(action, dict):
            action = {"type": "none", "content": "", "reason": ""}
        action_type = str(action.get("type", "none")).strip().lower()
        content = str(action.get("content", ""))
        reason = str(action.get("reason", "")).strip()
        if action_type == "insert_at_cursor":
            action_type = "replace_selection"
        if action_type not in ("none", "replace_selection", "replace_document"):
            action_type = "none"
            content = ""
        if action_type != "none" and not content.strip():
            action_type = "none"
            content = ""

        action_id = datetime.now(timezone.utc).strftime("ai-%Y%m%d%H%M%S%f")
        safe_action = {
            "type": action_type,
            "content": content,
            "reason": reason,
            "action_id": action_id,
            "user_message": (user_message or "").strip(),
        }
        self.ai_chat_pending_actions[tab_doc_id] = safe_action
        visible_text = self._compose_assistant_chat_text(assistant_message, safe_action)
        if visible_text:
            self._append_chat_message("assistant", visible_text, tab_index=tab_index)
        self._render_current_chat_history()

        self._append_ai_audit_log(
            status="proposed",
            action_type=action_type,
            user_message=user_message,
            content=content,
            reason=reason,
            action_id=action_id,
            doc_id=tab_doc_id,
        )

        if action_type == "none":
            self.ai_agent_status_var.set("Reply received")
        else:
            self.ai_agent_status_var.set("Suggestion ready to apply (preview shown in chat)")

    def _fail_ai_agent_response(self, error_message):
        """Finalize a failed AI agent request."""

        self._chat_busy = False
        self._ai_send_btn.configure(state=tk.NORMAL)
        self.ai_agent_status_var.set("")
        dialogs.Messagebox.show_error("AI Agent", f"Request failed: {error_message}")

    def _compose_assistant_chat_text(self, assistant_message, action):
        """Build chat-visible assistant text, including suggested content preview."""

        base_message = (assistant_message or "").strip() or "(No assistant response.)"
        if not isinstance(action, dict):
            return base_message

        action_type = str(action.get("type", "none")).strip().lower()
        if action_type == "insert_at_cursor":
            action_type = "replace_selection"
        content = str(action.get("content", "")).strip()
        if action_type not in ("replace_selection", "replace_document") or not content:
            return base_message

        normalized_base = re.sub(r"\s+", " ", base_message).strip().lower()
        normalized_content = re.sub(r"\s+", " ", content).strip().lower()
        if normalized_base and normalized_base == normalized_content:
            return base_message

        preview_limit = 2400
        preview = content if len(content) <= preview_limit else content[:preview_limit] + "\n..."
        return (
            f"{base_message}\n\n"
            f"Proposed content preview ({action_type}):\n"
            f"{preview}"
        )

    def _validate_ai_action_payload(self, action):
        """Validate AI action payload before applying to the editor."""

        if not isinstance(action, dict):
            return False, "Invalid action payload."

        action_type = str(action.get("type", "none")).strip().lower()
        if action_type == "insert_at_cursor":
            action_type = "replace_selection"
        if action_type not in ("replace_selection", "replace_document"):
            return False, "No applicable action."

        content = str(action.get("content", ""))
        if not content.strip():
            return False, "Action content is empty."
        if "\x00" in content:
            return False, "Action contains invalid null bytes."
        if len(content) > 20000:
            return False, "Action content is too large; please refine your request."
        return True, ""

    def apply_ai_agent_action(self):
        """Apply AI-generated editor action with validation checks."""

        text_area = self.get_current_text_area()
        if not text_area:
            return

        doc_id = self._get_document_id_for_tab()
        if not doc_id:
            return
        action = self.ai_chat_pending_actions.get(doc_id)
        ok, reason = self._validate_ai_action_payload(action)
        if not ok:
            dialogs.Messagebox.show_info("AI Agent", reason)
            return

        action_type = action["type"]
        content = action["content"]
        action_reason = (action.get("reason") or "").strip()
        action_id = (action.get("action_id") or "").strip()
        user_message = (action.get("user_message") or "").strip()

        prompt = "Apply this AI suggestion to the editor?"
        if action_reason:
            prompt += f"\n\nReason: {action_reason}"
        prompt += f"\n\nAction: {action_type}\nCharacters: {len(content)}"
        if not messagebox.askyesno("Apply AI Suggestion", prompt):
            self._append_ai_audit_log(
                status="rejected",
                action_type=action_type,
                user_message=user_message,
                content=content,
                reason=action_reason or "user_declined_confirmation",
                related_action_id=action_id,
                doc_id=doc_id,
            )
            return

        try:
            text_area.edit_separator()
            if action_type == "replace_document":
                text_area.delete("1.0", "end-1c")
                text_area.insert("1.0", content)
            else:
                try:
                    start_idx = text_area.index("sel.first")
                    end_idx = text_area.index("sel.last")
                except tk.TclError:
                    dialogs.Messagebox.show_info("AI Agent", "Please select a section to replace.")
                    return
                text_area.delete(start_idx, end_idx)
                text_area.insert(start_idx, content)

            text_area.edit_separator()
            idx = self.notebook.index(self.notebook.select())
            self.mark_tab_modified(idx)
            self.update_preview()

            self.ai_chat_pending_actions[doc_id] = {"type": "none", "content": "", "reason": ""}
            self._render_current_chat_history()
            self.ai_agent_status_var.set("Suggestion applied")
            self.ai_last_applied_action_id_by_doc[doc_id] = action_id
            self._append_ai_audit_log(
                status="applied",
                action_type=action_type,
                user_message=user_message,
                content=content,
                reason=action_reason,
                related_action_id=action_id,
                doc_id=doc_id,
            )
        except Exception as exc:
            self._append_ai_audit_log(
                status="failed",
                action_type=action_type,
                user_message=user_message,
                content=content,
                reason=str(exc),
                related_action_id=action_id,
                doc_id=doc_id,
            )
            dialogs.Messagebox.show_error("AI Agent", f"Failed to apply suggestion: {exc}")

    def reject_ai_agent_action(self):
        """Reject and clear the current pending AI suggestion."""

        doc_id = self._get_document_id_for_tab()
        if not doc_id:
            return

        action = self.ai_chat_pending_actions.get(doc_id)
        ok, reason = self._validate_ai_action_payload(action)
        if not ok:
            dialogs.Messagebox.show_info("AI Agent", reason)
            return

        action_type = action["type"]
        content = action["content"]
        action_reason = (action.get("reason") or "").strip()
        action_id = (action.get("action_id") or "").strip()
        user_message = (action.get("user_message") or "").strip()

        if not messagebox.askyesno("Reject AI Suggestion", "Reject and clear this AI suggestion?"):
            return

        self.ai_chat_pending_actions[doc_id] = {"type": "none", "content": "", "reason": ""}
        self._render_current_chat_history()
        self.ai_agent_status_var.set("Suggestion rejected")
        self._append_ai_audit_log(
            status="rejected",
            action_type=action_type,
            user_message=user_message,
            content=content,
            reason=action_reason or "rejected_from_button",
            related_action_id=action_id,
            doc_id=doc_id,
        )

    def undo_last_ai_action(self):
        """Undo one editor step and log it as AI-task rollback."""

        text_area = self.get_current_text_area()
        if not text_area:
            return

        doc_id = self._get_document_id_for_tab()
        if not doc_id:
            return

        last_action_id = (self.ai_last_applied_action_id_by_doc.get(doc_id) or "").strip()
        if not last_action_id:
            dialogs.Messagebox.show_info(
                "Undo AI Task",
                "No applied AI task found for this document.",
            )
            return

        if not messagebox.askyesno(
            "Undo AI Task",
            "This performs one Undo step in the editor for the last applied AI task.",
        ):
            return

        try:
            text_area.edit_undo()
            idx = self.notebook.index(self.notebook.select())
            self.mark_tab_modified(idx)
            self.update_preview()
            self.ai_agent_status_var.set("Last AI task undone")
            self._append_ai_audit_log(
                status="undone",
                action_type="undo",
                reason="undo_last_ai_task",
                related_action_id=last_action_id,
                doc_id=doc_id,
            )
        except tk.TclError:
            dialogs.Messagebox.show_info("Undo AI Task", "No undo step is currently available.")

    def _format_shortcut_pattern(self, pattern):
        """
        Converts a Tk key binding pattern into a human-readable shortcut label.

        :param str pattern: The Tk event pattern to format.

        :return: A str containing the formatted shortcut label, or an empty string when no pattern is provided.

        :raises AttributeError: If a non-string pattern is provided and does not support string operations.
        """

        if not pattern:
            return ""

        cleaned = pattern.strip("<>")
        parts = [part for part in cleaned.split("-") if part]
        pretty_parts = []

        for part in parts:
            lowered = part.lower()

            if lowered == "keypress":
                continue
            if lowered == "control":
                pretty_parts.append("Ctrl")
                continue
            if lowered == "command":
                pretty_parts.append("Cmd")
                continue
            if lowered in ("option", "alt"):
                pretty_parts.append("Alt")
                continue
            if lowered == "shift":
                pretty_parts.append("Shift")
                continue

            if part.startswith("F") and part[1:].isdigit():
                pretty_parts.append(part)
            elif len(part) == 1:
                pretty_parts.append(part.upper())
            else:
                pretty_parts.append(part)

        return "+".join(pretty_parts)

    def open_ai_data_folder(self):
        """Open the per-user AI data folder that stores settings, chat history, and audit logs."""

        try:
            data_dir = APP_SETTINGS_FILE_PATH.parent
            data_dir.mkdir(parents=True, exist_ok=True)

            path_str = str(data_dir)
            if sys.platform == "darwin":
                subprocess.Popen(["open", path_str])
            elif sys.platform.startswith("win"):
                os.startfile(path_str)
            else:
                subprocess.Popen(["xdg-open", path_str])
        except Exception as exc:
            dialogs.Messagebox.show_error("AI Data Folder", f"Failed to open folder: {exc}")

    def _on_drop_files(self, event):
        """
        Handles file drop events.

        :param event event: The file drop event to be processed.

        :raises RuntimeError: If the error handling drop fails.
        """

        print(f"🔍 Drop event triggered")
        print(f"   Event data type: {type(event.data)}")
        print(f"   Event data: {event.data}")

        try:
            drop_file(event, self)
        except Exception as e:
            print(f"❌ Error handling drop: {e}")
            import traceback

            traceback.print_exc()

    def new_file(self):
        """
        Create a new editor tab and register editor-scoped behavior.

        :return: A None value after the new editor tab is created and configured.

        :raises tk.TclError: If the editor widget or tab cannot be created.
        """

        frame = tk.Frame(self.notebook)
        base_font = (self.current_font_family, self.current_font_size)
        text_area = self.get_current_text_area()
        text_area = ScrolledText(frame, wrap=tk.WORD, font=base_font, undo=True)
        text_area.pack(fill=tk.BOTH, expand=True)

        # Zoom bindings must be widget-level (not bind_all) so "break" can
        # suppress the Text class's built-in scroll and scan-drag handlers.
        text_area.bind("<MouseWheel>", self._on_ctrl_scroll)
        text_area.bind("<Button-4>", self._on_linux_scroll)
        text_area.bind("<Button-5>", self._on_linux_scroll)
        text_area.bind("<Button-2>", self._on_middle_press)
        text_area.bind("<B2-Motion>", self._on_middle_drag)
        text_area.bind("<ButtonRelease-2>", self._on_middle_release)

        for _shortcut_name, pattern, handler in self.editor_shortcuts:
            text_area.bind(
                pattern,
                lambda event, handler=handler: (handler(), "break")[1],
            )

        # Setup IME interception
        wid = str(text_area)
        self._ime_states[wid] = {"active": False}

        def intercept_key(event):
            """
            Detects when a key has been pressed and updates the document accordingly.

            :param event event: The keypress event.

            :return: A None value.
            """

            state = self._ime_states[wid]

            # Detect IME activation (macOS IME emits empty char with keycode 0)
            if event.char == "" and event.keycode == 0:
                state["active"] = True
                return None

            # Deletion should mark modified but must not toggle IME state
            if event.keysym in ("BackSpace", "Delete"):
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass
                return None

            # Detect IME deactivation (non-ASCII = committed text)
            if event.char and ord(event.char) > 127:
                state["active"] = False
                # Mark tab as modified when committed Japanese text arrives
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass
                return None

            # For lowercase ASCII letters during IME, delete them immediately
            if state["active"] and event.char:
                if event.char.islower() and event.char.isalpha():
                    # Delete with highest priority (0 delay)
                    text_area.after(0, lambda: delete_ime_char())
            # For regular (non-IME) text input, mark as modified
            elif event.char and not state["active"]:
                if not self._loading_file:
                    try:
                        idx = self.notebook.index(self.notebook.select())
                        self.mark_tab_modified(idx)
                    except:
                        pass

            return None

        def delete_ime_char():
            """
            Takes the most recently inserted character, and if its a lowercase letter (IME composition character), delete it.
            """

            try:
                # Get current cursor position
                current_index = text_area.index("insert")
                # Calculate previous position
                line, col = current_index.split(".")
                prev_col = int(col) - 1
                if prev_col >= 0:
                    prev_index = f"{line}.{prev_col}"
                    # Get the character that was just inserted
                    char = text_area.get(prev_index, current_index)
                    # Delete it if it's a lowercase letter (IME composition character)
                    if char and len(char) == 1 and char.islower() and char.isalpha():
                        text_area.delete(prev_index, current_index)
            except Exception:
                pass

        # Bind KeyPress DIRECTLY with priority
        text_area.bind("<KeyPress>", intercept_key, add=False)

        # Other bindings come after
        self.notebook.add(frame, text="")
        tab_index = len(self.editors)
        self.notebook.select(tab_index)
        self.editors.append(text_area)
        self.file_paths.append(None)
        self._untitled_counter += 1
        self.tab_document_ids.append(f"untitled:{self._untitled_counter}")

        self.notebook.tab(tab_index, text="Untitled")
        self._render_current_chat_history()

    def open_file(self):
        """
        Handles opening a file and sets up its file handler.
        """

        file_path = filedialog.askopenfilename(
            filetypes=[
                ("Markdown files", "*.md *.MD"),
                ("HTML files", "*.html *.HTML *.htm *.HTM"),
                ("PDF files", "*.pdf *.PDF"),
                ("All files", "*.*"),
            ]
        )
        if file_path and (
            file_path.lower().endswith(".md")
            or file_path.lower().endswith((".html", ".htm", ".pdf"))
        ):
            abs_path = os.path.abspath(file_path)
            self.md_filepath_list = []
            self.md_filepath_list.append(abs_path)
            if abs_path in self.file_paths:
                index = self.file_paths.index(abs_path)
                self.notebook.select(index)
                self.load_file(abs_path)
                self.start_watching(abs_path)
                return

            self.new_file()
            self.load_file(abs_path)
            self.start_watching(abs_path)

    def load_file(self, path):
        """
        Loads the file from the given path and converts it to Markdown.

        :param string path: The path for the file to load.

        :raises RuntimeError: If the file fails to load.
        """

        abs_path = os.path.abspath(path)
        idx = self.notebook.index(self.notebook.select())
        text_area = self.get_current_text_area()
        is_html = abs_path.lower().endswith((".html", ".htm"))
        is_pdf = abs_path.lower().endswith(".pdf")

        try:
            # Set loading flag to prevent marking as modified
            self._loading_file = True

            # Check if file is PDF and convert to Markdown
            if is_pdf:
                if self.use_docling_pdf:
                    content = convert_pdf_to_markdown_docling(abs_path)
                else:
                    content = convert_pdf_to_markdown(abs_path)
            else:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()

                # Check if file is HTML and convert to Markdown
                if is_html:
                    content = convert_html_to_markdown(content)

            # Clear the text area and insert new content
            text_area.delete("1.0", tk.END)
            text_area.insert(tk.END, content)

            # Reset the modified flag
            text_area.edit_modified(False)

            # Update tab info and save state
            if is_html or is_pdf:
                # Update tab name to show it's converted
                base_name = os.path.splitext(os.path.basename(abs_path))[0]
                tab_text = f"{base_name}.md (converted)"
                self.notebook.tab(idx, text=tab_text)
                # Don't set file_paths to HTML/PDF file - treat as new unsaved file
                self.file_paths[idx] = None
                self.current_file_path = None
            else:
                self.file_paths[idx] = abs_path
                tab_text = os.path.basename(abs_path)
                self.notebook.tab(idx, text=tab_text)
                self.current_file_path = abs_path

            if 0 <= idx < len(self.tab_document_ids):
                old_doc_id = self.tab_document_ids[idx]
                self.tab_document_ids[idx] = abs_path
                self._migrate_chat_document_key(old_doc_id, abs_path)
        except Exception as e:
            dialogs.Messagebox.show_error("Error", f"Failed to load file: {e}")
        finally:
            # Always clear the loading flag first
            self._loading_file = False

            # Delay marking tab state to ensure all events are processed
            # Use after_idle to run after all pending events in the queue
            if is_html or is_pdf:
                # Mark as modified since it's converted content
                self.root.after(100, lambda: self.mark_tab_modified(idx))
            else:
                # Mark as saved since we just loaded from file
                self.root.after(100, lambda: self.mark_tab_saved(idx))

    def close_current_tab(self):
        """
        Closes the current tab and lets the notebook forget it.
        """

        if not self.editors:
            return
        idx = self.notebook.index(self.notebook.select())

        # Remove from modified tabs if present
        if idx in self.modified_tabs:
            self.modified_tabs.remove(idx)

        # Update indices in modified_tabs for tabs after the closed one
        self.modified_tabs = {i if i < idx else i - 1 for i in self.modified_tabs}

        self.notebook.forget(idx)
        del self.editors[idx]
        del self.file_paths[idx]
        if idx < len(self.tab_document_ids):
            del self.tab_document_ids[idx]
        self._render_current_chat_history()

    def close_all_tabs(self):
        """
        Closes all tabs and empties the notebook.
        """

        while self.editors:
            self.notebook.forget(0)
            del self.editors[0]
            del self.file_paths[0]
            if self.tab_document_ids:
                del self.tab_document_ids[0]
        # Clear modified tabs set
        self.modified_tabs.clear()
        self._render_current_chat_history()

    def show_tab_context_menu(self, event):
        """
        Shows the context menu when right-clicking on a tab.

        :param event event: The click event to be handled.

        :raises RuntimeError: If there is an error when attempting to display the context menu.
        """

        try:
            # Identify which tab was clicked
            clicked_tab = self.notebook.tk.call(
                self.notebook._w, "identify", "tab", event.x, event.y
            )
            if clicked_tab != "":
                # Store the clicked tab index for later use
                self.right_clicked_tab_index = int(clicked_tab)
                # Show the context menu at cursor position
                self.tab_context_menu.post(event.x_root, event.y_root)
        except Exception as e:
            print(f"Error showing context menu: {e}")

    def close_tab_from_context_menu(self):
        """
        Close the tab that was right-clicked.
        """

        if hasattr(
            self, "right_clicked_tab_index"
        ) and self.right_clicked_tab_index < len(self.editors):
            self.close_tab_by_index(self.right_clicked_tab_index)

    def close_tab_by_index(self, idx):
        """
        Closes the tab at the specified index.

        :param int idx: The index of the tab to be closed.
        """

        if idx < len(self.editors):
            # Remove from modified tabs if present
            if idx in self.modified_tabs:
                self.modified_tabs.remove(idx)

            # Update indices in modified_tabs for tabs after the closed one
            self.modified_tabs = {i if i < idx else i - 1 for i in self.modified_tabs}

            self.notebook.forget(idx)
            del self.editors[idx]
            del self.file_paths[idx]
            if idx < len(self.tab_document_ids):
                del self.tab_document_ids[idx]

            # Update tab_widgets dictionary
            if hasattr(self, "tab_widgets"):
                # Remove the closed tab
                if idx in self.tab_widgets:
                    del self.tab_widgets[idx]
                # Update indices for remaining tabs
                new_widgets = {}
                for key, value in self.tab_widgets.items():
                    new_key = key if key < idx else key - 1
                    new_widgets[new_key] = value
                self.tab_widgets = new_widgets
            self._render_current_chat_history()

    def start_watching(self, path):
        """
        Sets up a watchdog.observers Observer instance to monitor the file for modifications.

        :param string path: The file path for the file to be monitored.
        """

        if self.observer:
            self.observer.stop()
            self.observer.join()

        event_handler = FileChangeHandler(self, path)
        self.observer = Observer()
        watch_dir = os.path.dirname(os.path.abspath(path))
        self.observer.schedule(event_handler, path=watch_dir, recursive=False)
        self.observer.start()

    def on_text_change(self):
        """
        When the text is changed, reapply all formatting and update the preview file.
        """

        self.highlight_markdown()
        self.update_preview()

    def toggle_dark_mode(self):
        """
        Toggles between light and dark mode.
        """

        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"

        for text_area in self.editors:
            text_area.config(bg=bg, fg=fg, insertbackground=fg)

    def highlight_markdown(self):
        """
        Removes all existing formatting and inserts new tags based on the updated Markdown syntax.
        Implementation in place for:
        - Headings (#, ##, ### ... to 6).
        - Bold or italic text.
        - Links, blockquotes, and inline code.
        - Lists (unordered and ordered).
        - Tables.
        """

        # Get the current editor
        text_area = self.get_current_text_area()
        content = text_area.get("1.0", tk.END)

        # Remove all previous tags
        for tag in text_area.tag_names():
            text_area.tag_remove(tag, "1.0", tk.END)

        # Use the selected font for highlighting
        import platform
        import tkinter.font

        system = platform.system()
        if system == "Darwin":  # macOS
            default_font = "Menlo"
        elif system == "Windows":
            default_font = "Consolas"
        else:  # Linux
            default_font = "Ubuntu Mono"
        font_name = getattr(self, "current_font_family", default_font)
        font_size = getattr(self, "current_font_size", 14)
        text_area.tag_configure(
            "heading", foreground="#333333", font=(font_name, font_size + 4, "bold")
        )
        text_area.tag_configure("bold", font=(font_name, font_size, "bold"))
        text_area.tag_configure("italic", font=(font_name, font_size, "italic"))
        text_area.tag_configure(
            "code",
            foreground="#d19a66",
            background="#f6f8fa",
            font=(font_name, font_size),
        )
        text_area.tag_configure("link", foreground="#2aa198", underline=True)
        text_area.tag_configure(
            "blockquote", foreground="#6a737d", font=(font_name, font_size, "italic")
        )
        text_area.tag_configure(
            "list", foreground="#b58900", font=(font_name, font_size, "bold")
        )
        # ADD THIS NEW LINE:
        text_area.tag_configure(
            "table", foreground="#0066cc", font=(font_name, font_size)
        )

        import re

        lines = content.splitlines(keepends=True)
        pos = 0
        for line in lines:
            start_idx = f"{pos + 1}.0"
            end_idx = f"{pos + 1}.end"
            # Headings: #, ##, ### ...
            if re.match(r"^#{1,6} ", line):
                text_area.tag_add("heading", start_idx, end_idx)
            # Blockquotes: >
            if re.match(r"^> ", line):
                text_area.tag_add("blockquote", start_idx, end_idx)
            # Lists: -, *, +, or numbered
            if re.match(r"^\s*([-*+] |\d+\. )", line):
                text_area.tag_add("list", start_idx, end_idx)
            # ADD THIS NEW BLOCK:
            # Table rows: | cell | cell |
            if "|" in line and line.strip().startswith("|"):
                text_area.tag_add("table", start_idx, end_idx)
            # Inline code: `code`
            for m in re.finditer(r"`([^`]+)`", line):
                s = f"{pos + 1}.{m.start()}"
                e = f"{pos + 1}.{m.end()}"
                text_area.tag_add("code", s, e)
            # Bold: **text** or __text__
            for m in re.finditer(r"(\*\*|__)(.*?)\1", line):
                s = f"{pos + 1}.{m.start(2)}"
                e = f"{pos + 1}.{m.end(2)}"
                text_area.tag_add("bold", s, e)
            # Italic: *text* or _text_ (not bold)
            for m in re.finditer(
                r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)|(?<!_)_(?!_)([^_]+)(?<!_)_(?!\*)",
                line,
            ):
                group = 1 if m.group(1) else 2
                s = f"{pos + 1}.{m.start(group)}"
                e = f"{pos + 1}.{m.end(group)}"
                text_area.tag_add("italic", s, e)
            # Links: [text](url)
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
                s = f"{pos + 1}.{m.start()}"
                e = f"{pos + 1}.{m.end()}"
                text_area.tag_add("link", s, e)
            pos += 1

    def mark_tab_modified(self, tab_index):
        """
        Marks a tab as having unsaved modifications.

        :param int tab_index: The index of the tab to be marked as modified.
        """

        if tab_index not in self.modified_tabs:
            self.modified_tabs.add(tab_index)
            # Get current tab title
            current_title = self.notebook.tab(tab_index, "text")
            # Add asterisk if not already present
            if not current_title.startswith("* "):
                self.notebook.tab(tab_index, text=f"* {current_title}")

    def mark_tab_saved(self, tab_index):
        """
        Marks a tab as saved and removes the unsaved indicator.

        :param int tab_index: The index of the tab to be marked as saved.
        """

        if tab_index in self.modified_tabs:
            self.modified_tabs.remove(tab_index)
        # Get current tab title and remove asterisk if present
        try:
            current_title = self.notebook.tab(tab_index, "text")
            if current_title.startswith("* "):
                current_title = current_title[2:]
            self.notebook.tab(tab_index, text=current_title)
        except:
            pass

    def quit(self):
        """
        Stops the file observer if it's running, and then quits the application.
        """

        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None

        try:
            self.root.quit()
        finally:
            try:
                self.root.destroy()
            except tk.TclError:
                pass

    def save_file(self):
        """
        Saves the current file. If the file has been previously saved, it will overwrite the existing file. If not, the user will be prompted to choose a save location and file name.

        :raises RuntimeError: If there is an error saving the file to current_path.
        :raises RuntimeError: If there is an error saving the file to the user-selected path.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]

        if current_path:
            try:
                content = text_area.get("1.0", "end-1c")
                with open(current_path, "w", encoding="utf-8") as f:
                    f.write(content)
                # Mark tab as saved
                self.mark_tab_saved(idx)
            except Exception as e:
                dialogs.Messagebox.show_error("Error", f"Failed to save file: {e}")
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                initialfile="default.md",
            )
            if file_path:
                try:
                    old_doc_id = self._get_document_id_for_tab(idx)
                    content = text_area.get("1.0", "end-1c")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.file_paths[idx] = file_path
                    abs_file_path = os.path.abspath(file_path)
                    if 0 <= idx < len(self.tab_document_ids):
                        self.tab_document_ids[idx] = abs_file_path
                    self._migrate_chat_document_key(old_doc_id, abs_file_path)
                    tab_text = os.path.basename(file_path)
                    self.notebook.tab(idx, text=tab_text)
                    # Mark tab as saved (will ensure no asterisk)
                    self.mark_tab_saved(idx)
                except Exception as e:
                    dialogs.Messagebox.show_error("Error", f"Failed to save file: {e}")

    # --- Toolbar functions ---
    def get_current_text_area(self):
        """
        Returns the current text editor in the active tab.

        :return: The text editor for the active tab, or None if there are no editors.
        """

        if not self.editors:
            return None
        idx = self.notebook.index(self.notebook.select())
        return self.editors[idx]

    def apply_style(self, style):
        """
        Applies the heading styles to the relevant lines, or removes the heading if it is normal text, then updates the preview.

        :param string style: The style to be applied, which can be "Heading 1", "Heading 2", or "Heading 3". Any other value will be treated as normal text and will remove heading formatting.

        :raises tk.TclError: If there is an error accessing the text area or its contents.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
        except tk.TclError:
            # No selection, use current line
            sel_start = text_area.index("insert linestart")
            sel_end = text_area.index("insert lineend")
        start_line = int(sel_start.split(".")[0])
        end_line = int(sel_end.split(".")[0])
        for line in range(start_line, end_line + 1):
            line_start = f"{line}.0"
            line_end = f"{line}.end"
            line_text = text_area.get(line_start, line_end)
            # Remove existing heading marks
            new_text = line_text.lstrip("# ").lstrip()
            if style == "Heading 1":
                new_text = "# " + new_text
            elif style == "Heading 2":
                new_text = "## " + new_text
            elif style == "Heading 3":
                new_text = "### " + new_text
            # else: Normal text, just remove heading
            text_area.delete(line_start, line_end)
            text_area.insert(line_start, new_text)
        self.update_preview()

    def apply_font(self, font_name):
        """
        Applies the selected font to the text area and updates the preview.

        :param string font_name: The name of the font to be applied.
        """

        # Change the font for all editors
        import tkinter.font

        # If font_name contains spaces and a style (e.g., 'Arial Light'), use only the first part as the family
        family = font_name.split()[0]
        size = self.font_size_var.get()
        font = tkinter.font.Font(family=family, size=size)
        for text_area in self.editors:
            text_area.configure(font=font)
        self.current_font_family = family
        self.update_preview()

    def change_font_size(self, delta):
        """
        Changes the font size by a given value (limited to a minimum of 6).

        :param int delta: The change in font size.
        """

        new_size = max(6, self.font_size_var.get() + delta)
        self.font_size_var.set(new_size)
        self.apply_font(self.font_var.get())
        self.current_font_size = new_size
        self.update_preview()

    def _on_ctrl_scroll(self, event):
        """
        Zooms font size when Ctrl is held, otherwise allows normal scrolling.
        When zooming, returns "break" to prevent default scroll.
        When scrolling, doesn't return "break" to allow scrollbar updates.

        :param Event event: The MouseWheel event.

        :return: A str "break" only when zooming, None when scrolling normally.
        """

        if event.state & 0x4:
            if event.delta > 0:
                self.change_font_size(1)
            else:
                self.change_font_size(-1)
            return "break"
        # For normal scrolling, don't return "break" to allow default behavior

    def _on_linux_scroll(self, event):
        """
        Zooms font size on Ctrl+scroll for Linux (Button-4/5 events),
        otherwise allows normal scrolling.

        :param Event event: The button event (num 4 = up, 5 = down).

        :return: A str "break" only when zooming, None when scrolling normally.
        """

        if event.state & 0x4:
            if event.num == 4:
                self.change_font_size(1)
            else:
                self.change_font_size(-1)
            return "break"
        # For normal scrolling, don't return "break" to allow default behavior

    def _on_middle_press(self, event):
        """
        Records the starting Y position and font size for middle-click drag zoom.

        :param Event event: The middle mouse button press event.

        :return: None to allow default scroll behavior.
        """

        self._zoom_drag_y = event.y_root
        self._zoom_drag_base_size = self.font_size_var.get()
        self._zoom_activated = False

    def _on_middle_drag(self, event):
        """
        Zooms font size based on vertical mouse movement while middle button
        is held. Moving up zooms in, moving down zooms out (10px per step).
        Only activates zoom with significant movement (>15px).

        :param Event event: The mouse motion event.

        :return: A str "break" only when actively zooming.
        """

        if not hasattr(self, "_zoom_drag_y"):
            return
        delta_px = self._zoom_drag_y - event.y_root

        # Only activate zoom if movement is significant
        if abs(delta_px) > 15:
            self._zoom_activated = True
            new_size = max(6, self._zoom_drag_base_size + delta_px // 10)
            if new_size != self.font_size_var.get():
                self.font_size_var.set(new_size)
                self.apply_font(self.font_var.get())
                self.current_font_size = new_size
            return "break"

    def _on_middle_release(self, event):
        """
        Cleans up drag state and refreshes the preview after middle-click zoom.

        :param Event event: The middle mouse button release event.

        :return: None to allow default behavior.
        """

        if hasattr(self, "_zoom_drag_y"):
            if hasattr(self, "_zoom_activated") and self._zoom_activated:
                self.update_preview()
            del self._zoom_drag_y
            del self._zoom_drag_base_size
            if hasattr(self, "_zoom_activated"):
                del self._zoom_activated

    def toggle_bold(self):
        """
        Takes the existing text area and adds/removes the bold Markdown syntax to toggle boldness.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already bold, remove **, else add **
            if (
                selected_text.startswith("**")
                and selected_text.endswith("**")
                and len(selected_text) > 4
            ):
                new_text = selected_text[2:-2]
            else:
                new_text = f"**{selected_text}**"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info(
                "No selection", "Please select text to make bold."
            )
            return
        self.update_preview()

    def toggle_italic(self):
        """
        Takes the existing text area and adds/removes the italic Markdown syntax to toggle italicness.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already italic, remove *, else add * (single asterisk)
            if (
                selected_text.startswith("*")
                and selected_text.endswith("*")
                and len(selected_text) > 2
            ) or (
                selected_text.startswith("_")
                and selected_text.endswith("_")
                and len(selected_text) > 2
            ):
                new_text = selected_text[1:-1]
            else:
                new_text = f"*{selected_text}*"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info(
                "No selection", "Please select text to make italic."
            )
            return
        self.update_preview()

    def toggle_underline(self):
        """
        Takes the existing text area and adds/removes the underline Markdown syntax to toggle underline.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # Use HTML <u> for underline in Markdown (not standard, but works in many renderers)
            if (
                selected_text.startswith("<u>")
                and selected_text.endswith("</u>")
                and len(selected_text) > 7
            ):
                new_text = selected_text[3:-4]
            else:
                new_text = f"<u>{selected_text}</u>"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            dialogs.Messagebox.show_info(
                "No selection", "Please select text to underline."
            )
            return
        self.update_preview()

    def choose_fg_color(self):
        """
        Prompts the user to select a foreground colour, then applies it to the preview.

        :raises tk.TclError: If there is no text selection to apply the color to, or if there is an error accessing the text area or its contents.
        """

        import re

        cd = dialogs.ColorChooserDialog()
        cd.show()
        result = cd.result
        if result:
            color_hex = result.hex if hasattr(result, "hex") else result
            text_area = self.get_current_text_area()
            if text_area:
                try:
                    sel_start = text_area.index("sel.first")
                    sel_end = text_area.index("sel.last")
                    selected_text = text_area.get(sel_start, sel_end)

                    if selected_text.strip() == "" or "\n" in selected_text:
                        dialogs.Messagebox.show_info(
                            "Tip",
                            "Please select single-line non-empty text to set color.",
                        )
                        return

                    cleaned_text = re.sub(
                        r'<span style="color:[^">]+?">(.*?)</span>',
                        r"\1",
                        selected_text,
                        flags=re.DOTALL,
                    )
                    new_text = f'<span style="color:{color_hex}">{cleaned_text}</span>'

                    text_area.delete(sel_start, sel_end)
                    text_area.insert(sel_start, new_text)

                    self.current_fg_color = color_hex
                    self.update_preview()
                except tk.TclError:
                    dialogs.Messagebox.show_info(
                        "No selection", "Please select text to color."
                    )

    def choose_bg_color(self):
        """
        Prompts the user to select a background colour, then applies it to the preview.
        """

        cd = dialogs.ColorChooserDialog()
        cd.show()
        color = cd.result
        if color:
            color = color.hex
            text_area = self.get_current_text_area()
            if text_area:
                text_area.config(bg=color)
                self.current_bg_color = color
                self.update_preview()

    def update_preview(self):
        """
        Checks that a file is open, and that there is a loaded text area, then updates the preview file.
        """

        if not self.current_file_path:
            return
        text_area = self.get_current_text_area()
        if not text_area:
            return
        update_preview(self)

    def undo_action(self):
        """
        Checks if there is a loaded text area, and that changes have been made, then attempts to undo the most recent change.

        :raises tk.TclError: If there is an error performing the undo operation, such as if there are no actions to undo.
        """

        text_area = self.get_current_text_area()
        if text_area:
            try:
                text_area.edit_undo()
            except tk.TclError:
                pass

    def redo_action(self):
        """
        Checks if there is a loaded text area, then attempts to redo the most recently undone change.

        :raises tk.TclError: If there is an error performing the redo operation, such as if there are no actions to redo.
        """

        text_area = self.get_current_text_area()
        if text_area:
            try:
                text_area.edit_redo()
            except tk.TclError:
                pass

    def _bind_search_dialog_shortcuts(self, widget):
        """
        Route editor undo/redo shortcuts through a search-dialog widget.
        """

        widget.bind("<Command-KeyPress-z>", lambda _e: (self.undo_action(), "break")[1])
        widget.bind("<Control-KeyPress-z>", lambda _e: (self.undo_action(), "break")[1])
        widget.bind("<Command-Shift-KeyPress-z>", lambda _e: (self.redo_action(), "break")[1])
        widget.bind("<Command-Shift-KeyPress-Z>", lambda _e: (self.redo_action(), "break")[1])
        widget.bind("<Control-Shift-KeyPress-z>", lambda _e: (self.redo_action(), "break")[1])
        widget.bind("<Control-Shift-KeyPress-Z>", lambda _e: (self.redo_action(), "break")[1])
        widget.bind("<Control-KeyPress-y>", lambda _e: (self.redo_action(), "break")[1])

    def _bind_search_dialog_shortcuts_recursive(self, widget):
        """
        Recursively apply search-dialog shortcut routing to a widget tree.
        """

        self._bind_search_dialog_shortcuts(widget)
        for child in widget.winfo_children():
            self._bind_search_dialog_shortcuts_recursive(child)

    def open_search_dialog(self):
        """
        Opens a VSCode-style search dialog for the active editor.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return

        if self._search_dialog and self._search_dialog.winfo_exists():
            self._search_dialog.deiconify()
            self._search_dialog.lift()
            if self._search_entry and self._search_entry.winfo_exists():
                self._search_entry.focus_set()
                self._search_entry.selection_range(0, tk.END)
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Search")
        dialog.transient(self.root)
        dialog.resizable(False, False)

        self._search_dialog = dialog

        # Match the insert-table dialog approach: fixed size and centered placement.
        dialog.geometry("960x280")
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        container = tk.Frame(dialog, relief=tk.RAISED, borderwidth=1)
        container.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        top_row = tk.Frame(container)
        top_row.pack(fill=tk.X, padx=10, pady=(10, 6))

        tk.Label(top_row, text="Find:", anchor="w").pack(side=tk.LEFT, padx=(0, 8))

        selected_text = ""
        try:
            selected_text = text_area.get("sel.first", "sel.last").strip()
        except tk.TclError:
            selected_text = ""

        initial_query = selected_text or self._last_search_query
        self._last_search_query = initial_query
        search_var = tk.StringVar(value=initial_query)

        entry_font = (self.current_font_family, max(13, self.current_font_size))

        search_entry = ttk.Entry(top_row, textvariable=search_var, width=42, font=entry_font)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._search_entry = search_entry

        ttkb.Button(
            top_row,
            text="↑",
            width=3,
            bootstyle=(INFO, OUTLINE),
            command=lambda: self.find_previous_match(),
        ).pack(side=tk.LEFT, padx=(8, 4))
        ttkb.Button(
            top_row,
            text="↓",
            width=3,
            bootstyle=(PRIMARY, OUTLINE),
            command=lambda: self.find_next_match(),
        ).pack(side=tk.LEFT, padx=(0, 4))

        ttkb.Button(
            top_row,
            text="Cancel",
            width=10,
            bootstyle=SECONDARY,
            command=self._close_search_dialog,
        ).pack(side=tk.LEFT, padx=(4, 0))

        hint_label = tk.Label(
            container,
            text="Enter: Next   Shift+Enter: Previous   Esc: Close",
            anchor="w",
            fg="#6f6f6f",
        )
        hint_label.pack(fill=tk.X, padx=10, pady=(2, 6))

        option_row = tk.Frame(container)
        option_row.pack(fill=tk.X, padx=10, pady=(0, 6))

        ttk.Checkbutton(
            option_row,
            text="Aa Match Case",
            variable=self._search_case_sensitive_var,
            command=lambda: self._refresh_search_matches(keep_current=False),
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            option_row,
            text="ab Whole Word",
            variable=self._search_whole_word_var,
            command=lambda: self._refresh_search_matches(keep_current=False),
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttk.Checkbutton(
            option_row,
            text=".* Use Regular Expression",
            variable=self._search_regex_var,
            command=lambda: self._refresh_search_matches(keep_current=False),
        ).pack(side=tk.LEFT)

        status_label = tk.Label(
            container,
            textvariable=self._search_status_var,
            anchor="w",
            fg="#2a6f97",
        )
        status_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        def on_query_change(*_args):
            self._last_search_query = search_var.get().strip()
            self._refresh_search_matches(keep_current=False)

        search_var.trace_add("write", on_query_change)

        search_entry.bind("<Return>", lambda _e: (self.find_next_match(), "break")[1])
        search_entry.bind("<KP_Enter>", lambda _e: (self.find_next_match(), "break")[1])
        search_entry.bind("<Shift-Return>", lambda _e: (self.find_previous_match(), "break")[1])

        dialog.bind("<Return>", lambda _e: (self.find_next_match(), "break")[1])
        dialog.bind("<KP_Enter>", lambda _e: (self.find_next_match(), "break")[1])
        dialog.bind("<Shift-Return>", lambda _e: (self.find_previous_match(), "break")[1])
        dialog.bind("<Escape>", lambda _e: self._close_search_dialog())
        dialog.protocol("WM_DELETE_WINDOW", self._close_search_dialog)

        search_entry.focus_set()
        search_entry.selection_range(0, tk.END)

        replace_row = tk.Frame(container)
        replace_row.pack(fill=tk.X, padx=10, pady=(0, 8))

        tk.Label(replace_row, text="Replace:", anchor="w").pack(side=tk.LEFT, padx=(0, 8))

        replace_var = tk.StringVar(value=self._last_replace_text)
        replace_entry = ttk.Entry(replace_row, textvariable=replace_var, width=42, font=entry_font)
        replace_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._replace_entry = replace_entry

        ttkb.Button(
            replace_row,
            text="Replace",
            width=10,
            bootstyle=SUCCESS,
            command=self.replace_current_match,
        ).pack(side=tk.LEFT, padx=(8, 4))
        ttkb.Button(
            replace_row,
            text="Replace All",
            width=12,
            bootstyle=PRIMARY,
            command=self.replace_all_matches,
        ).pack(side=tk.LEFT, padx=(0, 0))

        replace_var.trace_add("write", lambda *_args: setattr(self, "_last_replace_text", replace_var.get()))

        self._bind_search_dialog_shortcuts_recursive(dialog)

        self._refresh_search_matches(keep_current=False)

    def open_replace_dialog(self):
        """
        Opens the search dialog and focuses the replace field.
        """

        self.open_search_dialog()
        if self._replace_entry and self._replace_entry.winfo_exists():
            self._replace_entry.focus_set()
            self._replace_entry.selection_range(0, tk.END)

    def _close_search_dialog(self):
        """
        Closes the search dialog and clears its visual highlights.
        """

        if self._search_dialog and self._search_dialog.winfo_exists():
            self._search_dialog.destroy()
        self._search_dialog = None
        self._search_entry = None
        self._replace_entry = None
        self._search_status_var.set("")

        text_area = self.get_current_text_area()
        if text_area:
            self._clear_search_highlight(text_area)

    def _is_search_dialog_active(self):
        """
        Returns True when the search dialog is currently open.
        """

        return bool(self._search_dialog and self._search_dialog.winfo_exists())

    def _refresh_search_matches(self, keep_current=True, prefer_backward=False):
        """
        Highlights all matches and optionally selects the next/previous current match.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return None

        query = (self._last_search_query or "").strip()

        previous_current = None
        if keep_current:
            current_ranges = text_area.tag_ranges("search_match_current")
            if len(current_ranges) >= 2:
                previous_current = (str(current_ranges[0]), str(current_ranges[1]))

        text_area.tag_configure("search_match_all", background="#d9e9ff", foreground="#000000")
        text_area.tag_configure("search_match_current", background="#ffd166", foreground="#000000")
        self._clear_search_highlight(text_area)

        if not query:
            self._search_status_var.set("Type to search in current document")
            return None

        compiled = self._build_search_regex(query)
        if compiled is None:
            return None

        content = text_area.get("1.0", "end-1c")
        matches = []
        for match in compiled.finditer(content):
            start_offset, end_offset = match.span()
            # Ignore zero-length matches to keep navigation stable.
            if end_offset <= start_offset:
                continue
            start_index = text_area.index(f"1.0+{start_offset}c")
            end_index = text_area.index(f"1.0+{end_offset}c")
            matches.append((start_index, end_index))
            text_area.tag_add("search_match_all", start_index, end_index)

        if not matches:
            self._search_status_var.set(f'No matches for "{query}"')
            return None

        current = previous_current

        if current is None:
            insert_index = text_area.index("insert")
            if prefer_backward:
                for start, end in reversed(matches):
                    if text_area.compare(start, "<", insert_index):
                        current = (start, end)
                        break
                if current is None:
                    current = matches[-1]
            else:
                for start, end in matches:
                    if text_area.compare(start, ">=", insert_index):
                        current = (start, end)
                        break
                if current is None:
                    current = matches[0]

        text_area.tag_add("search_match_current", current[0], current[1])
        self._search_status_var.set(f"{len(matches)} match(es)")
        return matches

    def _build_search_regex(self, query):
        """
        Builds a compiled regex from current search options.
        """

        flags = 0 if self._search_case_sensitive_var.get() else re.IGNORECASE
        use_regex = self._search_regex_var.get()
        whole_word = self._search_whole_word_var.get()

        pattern = query if use_regex else re.escape(query)
        if whole_word:
            pattern = rf"\b(?:{pattern})\b"

        try:
            return re.compile(pattern, flags)
        except re.error as exc:
            self._search_status_var.set(f"Invalid regex: {exc}")
            return None

    def _clear_search_highlight(self, text_area):
        """
        Clears the search highlight tag in the given text widget.
        """

        text_area.tag_remove("search_match_all", "1.0", tk.END)
        text_area.tag_remove("search_match_current", "1.0", tk.END)

    def _select_from_matches(self, matches, forward=True):
        """
        Selects the next or previous match from prepared match positions.
        """

        text_area = self.get_current_text_area()
        if not text_area or not matches:
            return

        current_ranges = text_area.tag_ranges("search_match_current")
        current_start = str(current_ranges[0]) if len(current_ranges) >= 2 else None

        if current_start is None:
            target = matches[0] if forward else matches[-1]
        else:
            indices = [i for i, (start, _) in enumerate(matches) if start == current_start]
            current_idx = indices[0] if indices else 0
            target_idx = (current_idx + 1) % len(matches) if forward else (current_idx - 1) % len(matches)
            target = matches[target_idx]

        text_area.tag_remove("search_match_current", "1.0", tk.END)
        text_area.tag_add("search_match_current", target[0], target[1])
        text_area.tag_remove(tk.SEL, "1.0", tk.END)
        text_area.tag_add(tk.SEL, target[0], target[1])
        text_area.mark_set("insert", target[1] if forward else target[0])
        text_area.see(target[0])

        # Keep focus in search box only when focus is already in the search UI.
        # This keeps Enter-to-next behavior for search typing, while still
        # allowing users to click and edit the document like VSCode.
        focus_widget = self.root.focus_get()
        focus_in_search_ui = False
        if self._is_search_dialog_active() and focus_widget is not None and self._search_dialog is not None:
            try:
                focus_in_search_ui = str(focus_widget).startswith(str(self._search_dialog))
            except Exception:
                focus_in_search_ui = False

        if focus_in_search_ui and self._search_entry and self._search_entry.winfo_exists():
            self._search_entry.focus_set()
            self._search_entry.icursor(tk.END)
        elif not focus_in_search_ui:
            text_area.focus_set()

    def find_previous_match(self):
        """
        Finds and highlights the previous occurrence of the current search query.
        """

        matches = self._refresh_search_matches(keep_current=True, prefer_backward=True)
        if matches:
            self._select_from_matches(matches, forward=False)

    def find_next_match(self):
        """
        Finds and highlights the next occurrence of the current search query.
        """

        matches = self._refresh_search_matches(keep_current=True, prefer_backward=False)
        if matches:
            self._select_from_matches(matches, forward=True)

    def replace_current_match(self):
        """
        Replaces the currently selected match and moves to the next match.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return

        matches = self._refresh_search_matches(keep_current=True, prefer_backward=False)
        if not matches:
            return

        current_ranges = text_area.tag_ranges("search_match_current")
        if len(current_ranges) < 2:
            self._select_from_matches(matches, forward=True)
            current_ranges = text_area.tag_ranges("search_match_current")
            if len(current_ranges) < 2:
                return

        start = str(current_ranges[0])
        end = str(current_ranges[1])
        matched_text = text_area.get(start, end)
        replace_text = self._last_replace_text

        if self._search_regex_var.get():
            query = (self._last_search_query or "").strip()
            if not query:
                return
            compiled = self._build_search_regex(query)
            if compiled is None:
                return
            replaced_text = compiled.sub(replace_text, matched_text, count=1)
        else:
            replaced_text = replace_text

        text_area.edit_separator()
        text_area.delete(start, end)
        text_area.insert(start, replaced_text)
        text_area.edit_separator()
        text_area.edit_modified(True)

        try:
            idx = self.notebook.index(self.notebook.select())
            self.mark_tab_modified(idx)
        except Exception:
            pass

        self.update_preview()
        text_area.mark_set("insert", f"{start}+{len(replaced_text)}c")
        if self._replace_entry and self._replace_entry.winfo_exists():
            self._replace_entry.focus_set()
            self._replace_entry.icursor(tk.END)
        self.find_next_match()

    def replace_all_matches(self):
        """
        Replaces all matches in the current editor.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return

        query = (self._last_search_query or "").strip()
        if not query:
            self._search_status_var.set("Type to search in current document")
            return

        compiled = self._build_search_regex(query)
        if compiled is None:
            return

        replace_text = self._last_replace_text
        content = text_area.get("1.0", "end-1c")
        replaced_content, count = compiled.subn(replace_text, content)

        if count == 0:
            self._search_status_var.set("No matches to replace")
            return

        text_area.edit_separator()
        text_area.delete("1.0", tk.END)
        text_area.insert("1.0", replaced_content)
        text_area.edit_separator()
        text_area.edit_modified(True)

        try:
            idx = self.notebook.index(self.notebook.select())
            self.mark_tab_modified(idx)
        except Exception:
            pass

        self.update_preview()
        self._search_status_var.set(f"Replaced {count} occurrence(s)")
        if self._replace_entry and self._replace_entry.winfo_exists():
            self._replace_entry.focus_set()
            self._replace_entry.icursor(tk.END)
        self._refresh_search_matches(keep_current=False)

    def _get_current_ai_provider(self):
        """Return the current runtime AI provider."""

        return (
            (self.ai_provider_var.get() or os.getenv("AI_PROVIDER", "openrouter"))
            .strip()
            .lower()
            or "openrouter"
        )

    def _request_translation_cancel(self):
        """Request cancellation of the running translation job."""
        self._translation_cancel_requested = True
        self.translation_status_var.set("Cancelling…")
        self._translation_cancel_btn.configure(state="disabled")

    def _show_translation_progress(self, total_steps, message):
        """Display the translation progress bar."""

        self._translation_cancel_requested = False
        safe_total = max(1, int(total_steps or 1))
        self.translation_progress.configure(maximum=safe_total)
        self.translation_progress_var.set(0)
        self.translation_status_var.set(message)
        self._translation_cancel_btn.configure(state="normal")
        if not self.translation_progress_frame.winfo_manager():
            self.translation_progress_frame.pack(fill=tk.X, before=self.notebook)

    def _update_translation_progress(self, current_step, total_steps, message):
        """Update the translation progress UI."""

        safe_total = max(1, int(total_steps or 1))
        self.translation_progress.configure(maximum=safe_total)
        self.translation_progress_var.set(min(current_step, safe_total))
        self.translation_status_var.set(message)

    def _hide_translation_progress(self):
        """Hide translation progress UI."""

        self.translation_progress_var.set(0)
        self.translation_status_var.set("")
        self._translation_cancel_btn.configure(state="disabled")
        if self.translation_progress_frame.winfo_manager():
            self.translation_progress_frame.pack_forget()

    def _show_ai_key_dialog(
        self,
        provider_name,
        prompt_message,
        allow_provider_change=False,
        allow_delete=True,
    ):
        """Prompt the user for an API key and optional secure persistence."""

        provider_options = ["openrouter", "openai", "anthropic"]
        initial_provider = (provider_name or self._get_current_ai_provider()).strip().lower()
        if initial_provider not in provider_options:
            initial_provider = "openrouter"

        dialog = tk.Toplevel(self.root)
        dialog.title("AI API Key")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        dialog.geometry("560x420")
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 280
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 210
        dialog.geometry(f"+{x}+{y}")

        container = ttk.Frame(dialog, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            container,
            text=prompt_message,
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 12))

        provider_var = tk.StringVar(value=initial_provider)
        stored_key_status_var = tk.StringVar(value="")
        result = {"confirmed": False}

        if allow_provider_change:
            ttk.Label(container, text="Provider:").pack(anchor="w")
            provider_combo = ttk.Combobox(
                container,
                values=[get_ai_provider_display_name(name) for name in provider_options],
                state="readonly",
                width=40,
            )
            provider_combo.current(provider_options.index(initial_provider))
            provider_combo.pack(anchor="w", pady=(4, 12))

            def sync_provider(*_args):
                provider_var.set(provider_options[provider_combo.current()])
                stored_key_status_var.set(
                    "Stored key status is checked only when needed to avoid system prompts."
                )

            provider_combo.bind("<<ComboboxSelected>>", sync_provider)
        else:
            ttk.Label(
                container,
                text=f"Provider: {get_ai_provider_display_name(initial_provider)}",
            ).pack(anchor="w", pady=(0, 12))

        ttk.Label(container, text="API Key:").pack(anchor="w")
        api_key_entry = ttk.Entry(container, width=62, show="*")
        api_key_entry.pack(anchor="w", pady=(4, 8))
        api_key_entry.focus_set()

        ttk.Label(
            container,
            textvariable=stored_key_status_var,
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 10))

        ttk.Label(
            container,
            text="Keys are stored in the system credential store (Keychain/Credential Manager/Secret Service).",
            foreground="gray",
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(6, 0))

        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(18, 0))

        def on_confirm():
            api_key = api_key_entry.get().strip()
            if not api_key:
                dialogs.Messagebox.show_error("Missing API Key", "Please enter an API key.")
                return

            result.update(
                {
                    "confirmed": True,
                    "provider_name": provider_var.get().strip().lower(),
                    "api_key": api_key,
                    "save_securely": True,
                    "delete_stored": False,
                }
            )
            dialog.destroy()

        def on_delete():
            result.update(
                {
                    "confirmed": True,
                    "provider_name": provider_var.get().strip().lower(),
                    "api_key": "",
                    "save_securely": False,
                    "delete_stored": True,
                }
            )
            dialog.destroy()

        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        if allow_delete:
            ttk.Button(button_frame, text="Remove", command=on_delete, width=12).grid(
                row=0, column=0, padx=4
            )
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy, width=12).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(button_frame, text="Save", command=on_confirm, width=12).grid(
            row=0, column=2, padx=4
        )

        stored_key_status_var.set(
            "Stored key status is checked only when needed to avoid system prompts."
        )
        dialog.bind("<Return>", lambda _event: on_confirm())
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        dialog.wait_window()

        if not result.get("confirmed"):
            return None

        return result

    def _apply_ai_key_dialog_result(self, result, show_feedback=False):
        """Apply API key changes selected in the dialog."""

        if not result:
            return False

        provider_name = (result.get("provider_name") or self._get_current_ai_provider()).strip().lower()
        env_var = get_ai_provider_env_var(provider_name)

        if result.get("delete_stored"):
            delete_secure_ai_api_key(provider_name)
            if env_var and env_var in os.environ:
                os.environ.pop(env_var, None)
            if show_feedback:
                dialogs.Messagebox.show_info(
                    "AI API Key",
                    f"Removed the stored key for {get_ai_provider_display_name(provider_name)}.",
                )
            return True

        api_key = (result.get("api_key") or "").strip()
        if not api_key:
            return False

        if env_var:
            os.environ[env_var] = api_key

        if result.get("save_securely"):
            set_secure_ai_api_key(provider_name, api_key)

        if show_feedback:
            storage_text = "saved securely" if result.get("save_securely") else "stored for this session only"
            dialogs.Messagebox.show_info(
                "AI API Key",
                f"The {get_ai_provider_display_name(provider_name)} key is now {storage_text}.",
            )

        return True

    def open_ai_provider_config(self):
        """Open the unified AI Provider & API Keys dialog."""

        providers = ["openrouter", "openai", "anthropic"]
        provider_labels = {"openrouter": "OpenRouter", "openai": "OpenAI", "anthropic": "Anthropic"}

        dialog = tk.Toplevel(self.root)
        dialog.title("AI Provider & API Keys")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)
        dialog.geometry("600x540")
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 300
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 270
        dialog.geometry(f"+{x}+{y}")

        container = ttk.Frame(dialog, padding=16)
        container.pack(fill=tk.BOTH, expand=True)

        # --- Provider selection ---
        ttk.Label(container, text="Provider:").pack(anchor="w")
        provider_var = tk.StringVar(value=self._get_current_ai_provider())
        provider_combo = ttk.Combobox(
            container,
            textvariable=provider_var,
            values=[provider_labels[p] for p in providers],
            state="readonly",
            width=30,
        )
        # Show display label in the combo
        provider_combo.set(provider_labels.get(provider_var.get(), "OpenRouter"))
        provider_combo.pack(anchor="w", pady=(4, 12))

        # --- Model selection ---
        ttk.Label(container, text="Model:").pack(anchor="w")
        model_var = tk.StringVar()
        model_combo = ttk.Combobox(container, textvariable=model_var, width=50)
        model_combo.pack(anchor="w", pady=(4, 4))

        fetch_status_var = tk.StringVar(value="")
        fetch_status_label = ttk.Label(
            container, textvariable=fetch_status_var, foreground="gray", wraplength=560
        )
        fetch_status_label.pack(anchor="w", pady=(0, 8))

        # --- API Key ---
        ttk.Label(container, text="API Key:").pack(anchor="w")
        api_key_entry = ttk.Entry(container, width=64, show="*")
        api_key_entry.pack(anchor="w", pady=(4, 4))

        stored_key_status_var = tk.StringVar(value="")
        ttk.Label(
            container,
            textvariable=stored_key_status_var,
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(0, 8))

        hint_var = tk.StringVar(value="")
        ttk.Label(
            container,
            textvariable=hint_var,
            foreground="gray",
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor="w", pady=(4, 0))

        # --- Buttons ---
        button_frame = ttk.Frame(container)
        button_frame.pack(fill=tk.X, pady=(18, 0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        button_frame.columnconfigure(2, weight=1)

        def _get_normalized_provider():
            label = provider_var.get()
            for p, lbl in provider_labels.items():
                if lbl == label:
                    return p
            return label.lower()

        def _refresh_ui(*_):
            pname = _get_normalized_provider()
            # Keep the persisted model visible even when it is not in the curated defaults.
            defaults = list(AI_PROVIDER_DEFAULT_MODELS.get(pname, []))
            current_model = (get_ai_provider_model(pname) or "").strip()
            model_values = list(defaults)
            if current_model and current_model not in model_values:
                model_values.insert(0, current_model)

            model_combo["values"] = model_values
            if current_model:
                model_var.set(current_model)
            else:
                model_var.set(model_values[0] if model_values else "")
            api_key_entry.delete(0, tk.END)
            stored_key_status_var.set(
                "Stored key status is checked only when needed to avoid system prompts."
            )
            hint_var.set(
                "Keys are stored in the system credential store. A prompt may appear when a key is accessed."
            )

        def _fetch_models_async(*_):
            pname = _get_normalized_provider()
            key = api_key_entry.get().strip() or get_secure_ai_api_key(pname)
            if not key:
                fetch_status_var.set("Enter an API key to fetch the live model list.")
                return
            fetch_status_var.set("Fetching model list…")
            model_combo.config(state="disabled")

            def worker():
                models = fetch_available_models(pname, key)
                def update():
                    model_combo.config(state="normal")
                    model_combo["values"] = models
                    cur = model_var.get()
                    if cur not in models:
                        model_var.set(models[0] if models else "")
                    fetch_status_var.set(f"{len(models)} models available.")
                dialog.after(0, update)

            threading.Thread(target=worker, daemon=True).start()

        def on_save():
            pname = _get_normalized_provider()
            new_key = api_key_entry.get().strip()
            chosen_model = model_var.get().strip()

            # Key handling
            if new_key:
                env_var = get_ai_provider_env_var(pname)
                if env_var:
                    os.environ[env_var] = new_key
                try:
                    set_secure_ai_api_key(pname, new_key)
                except Exception as exc:
                    dialogs.Messagebox.show_error("Key Storage", f"Could not save key: {exc}")
                    return

            # Model handling
            if chosen_model:
                set_ai_provider_model(pname, chosen_model)

            # Switch provider
            self.ai_provider_var.set(pname)
            set_current_ai_provider(pname)

            dialog.destroy()
            dialogs.Messagebox.show_info(
                "Settings Saved",
                f"Provider: {provider_labels.get(pname, pname)}\nModel: {chosen_model or '(unchanged)'}",
            )

        def on_delete_key():
            pname = _get_normalized_provider()
            try:
                delete_secure_ai_api_key(pname)
            except Exception:
                pass
            env_var = get_ai_provider_env_var(pname)
            if env_var and env_var in os.environ:
                del os.environ[env_var]
            api_key_entry.delete(0, tk.END)
            stored_key_status_var.set("Stored key deleted.")
            hint_var.set(
                "Keys are stored in the system credential store. A prompt may appear when a key is accessed."
            )

        ttk.Button(button_frame, text="Delete Key", command=on_delete_key, width=12).grid(
            row=0, column=0, padx=4
        )
        ttk.Button(button_frame, text="Fetch Models", command=_fetch_models_async, width=12).grid(
            row=0, column=1, padx=4
        )
        ttk.Button(button_frame, text="Save", command=on_save, width=12).grid(
            row=0, column=2, padx=4
        )

        provider_combo.bind("<<ComboboxSelected>>", _refresh_ui)
        _refresh_ui()

        dialog.bind("<Return>", lambda _e: on_save())
        dialog.bind("<Escape>", lambda _e: dialog.destroy())
        dialog.wait_window()

    # Keep the old name as an alias so _request_translation_api_key still works
    def open_ai_key_manager(self):
        self.open_ai_provider_config()

    def _request_translation_api_key(self, config_error):
        """Prompt for an API key from a worker thread via the unified config dialog."""

        dialog_done = threading.Event()
        provider_name = (getattr(config_error, "provider_name", None) or self._get_current_ai_provider()).strip().lower()

        def show_dialog():
            self.open_ai_provider_config()
            dialog_done.set()

        self.root.after(0, show_dialog)
        dialog_done.wait()

        # Return a synthetic "confirmed" dict so the translation worker retries.
        env_var = get_ai_provider_env_var(provider_name)
        has_key = bool(
            (env_var and os.environ.get(env_var, "").strip())
            or get_secure_ai_api_key(provider_name)
        )
        if has_key:
            return {"confirmed": True, "provider_name": provider_name}
        return None

    def _prepare_translation_session(
        self, tab_index, text_area, start_idx, end_idx, source_text, total_chunks
    ):
        """Prepare the editor for progressive translation output."""

        self._translation_session_counter += 1
        mark_name = f"translation_insert_{self._translation_session_counter}"
        text_area.edit_separator()
        text_area.delete(start_idx, end_idx)
        text_area.mark_set(mark_name, start_idx)
        text_area.mark_gravity(mark_name, tk.RIGHT)
        text_area.see(start_idx)
        text_area.focus_set()
        self._show_translation_progress(total_chunks, f"Preparing translation... 0/{total_chunks}")
        return {
            "tab_index": tab_index,
            "text_area": text_area,
            "start_idx": start_idx,
            "mark_name": mark_name,
            "source_text": source_text,
            "inserted_chunks": 0,
            "total_chunks": total_chunks,
        }

    def _append_translation_chunk(self, session, translated_chunk, chunk_index):
        """Insert one translated chunk and keep the editor focused on that region."""

        text_area = session["text_area"]
        text_area.insert(session["mark_name"], translated_chunk)
        session["inserted_chunks"] = chunk_index
        self.mark_tab_modified(session["tab_index"])
        text_area.see(session["mark_name"])
        self.update_preview()
        self._update_translation_progress(
            chunk_index,
            session["total_chunks"],
            f"Translated chunk {chunk_index}/{session['total_chunks']}",
        )

    def _finish_translation_session(self, session, ambiguity_notes):
        """Finalize the progressive translation session."""

        text_area = session["text_area"]
        try:
            text_area.mark_unset(session["mark_name"])
        except tk.TclError:
            pass
        text_area.edit_separator()
        self.update_preview()
        self.root.config(cursor="")
        self.translation_job_active = False
        self._hide_translation_progress()

        unique_notes = []
        seen_notes = set()
        for note in ambiguity_notes:
            cleaned = str(note).strip()
            if cleaned and cleaned not in seen_notes:
                unique_notes.append(cleaned)
                seen_notes.add(cleaned)

        if unique_notes:
            dialogs.Messagebox.show_info(
                "Translation completed with notes:\n\n" + "\n".join(f"- {note}" for note in unique_notes),
                "Translation Notes",
            )

    def _fail_translation_session(self, session, error_message):
        """Restore or keep partial editor content after a translation failure."""

        text_area = session["text_area"]
        if session["inserted_chunks"] == 0:
            text_area.insert(session["start_idx"], session["source_text"])
            followup = "The original text was restored."
        else:
            followup = "Partial translated output has been kept in the editor."

        try:
            text_area.mark_unset(session["mark_name"])
        except tk.TclError:
            pass

        text_area.edit_separator()
        self.update_preview()
        self.root.config(cursor="")
        self.translation_job_active = False
        self._hide_translation_progress()
        dialogs.Messagebox.show_error(
            f"{error_message}\n\n{followup}",
            "AI Translation Failed",
        )

    def _prompt_translation_languages(self):
        """
        Prompts user for source and target languages for AI translation.

        :return: Tuple (source_language, target_language) or (None, None) when cancelled.
        """

        # Create custom dialog with comboboxes
        dialog = tk.Toplevel(self.root)
        dialog.title("AI Translation - Select Languages")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog on parent
        dialog.geometry("400x280")
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - 200
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - 140
        dialog.geometry(f"+{x}+{y}")

        result = {"source": None, "target": None, "confirmed": False}

        # Source language
        ttk.Label(dialog, text="Source Language:").pack(pady=(20, 5))
        source_combo = ttk.Combobox(
            dialog, values=self.translation_languages, state="readonly", width=30
        )
        if self.translation_source_language in self.translation_languages:
            source_combo.set(self.translation_source_language)
        else:
            source_combo.current(0)
        source_combo.pack(pady=5)

        # Target language
        ttk.Label(dialog, text="Target Language:").pack(pady=(10, 5))
        target_combo = ttk.Combobox(
            dialog, values=self.translation_languages, state="readonly", width=30
        )
        if self.translation_target_language in self.translation_languages:
            target_combo.set(self.translation_target_language)
        else:
            target_combo.current(1)
        target_combo.pack(pady=5)

        def on_ok():
            result["source"] = source_combo.get()
            result["target"] = target_combo.get()
            result["confirmed"] = True
            dialog.destroy()

        def on_cancel():
            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="OK", command=on_ok, width=10).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(button_frame, text="Cancel", command=on_cancel, width=10).pack(
            side=tk.LEFT, padx=5
        )

        # Bind Enter and Escape keys
        dialog.bind("<Return>", lambda e: on_ok())
        dialog.bind("<Escape>", lambda e: on_cancel())

        # Wait for dialog to close
        dialog.wait_window()

        if not result["confirmed"]:
            return None, None

        self.translation_source_language = result["source"].strip()
        self.translation_target_language = result["target"].strip()
        return self.translation_source_language, self.translation_target_language

    def _get_translation_scope(self, text_area, selected_only):
        """
        Determines translation range and text based on selected scope.

        :param ScrolledText text_area: Active text editor.
        :param bool selected_only: True for selected text, False for full document.

        :return: Tuple (start_idx, end_idx, source_text).
        """

        if selected_only:
            try:
                start_idx = text_area.index("sel.first")
                end_idx = text_area.index("sel.last")
            except tk.TclError:
                dialogs.Messagebox.show_info(
                    "No selection", "Please select text before translating."
                )
                return None, None, None
        else:
            start_idx = "1.0"
            end_idx = "end-1c"

        source_text = text_area.get(start_idx, end_idx)
        if not source_text.strip():
            dialogs.Messagebox.show_info(
                "Empty content", "Nothing to translate in the chosen scope."
            )
            return None, None, None

        return start_idx, end_idx, source_text

    def _apply_translation_result(
        self, tab_index, text_area, start_idx, end_idx, translated_text, ambiguity_notes
    ):
        """
        Applies translated content back to the editor and keeps undo/redo usable.
        """

        try:
            text_area.edit_separator()
            text_area.delete(start_idx, end_idx)
            text_area.insert(start_idx, translated_text)
            text_area.edit_separator()

            self.mark_tab_modified(tab_index)
            self.update_preview()

            if ambiguity_notes:
                note_text = "\n".join([f"- {note}" for note in ambiguity_notes])
                dialogs.Messagebox.show_info(
                    "Translation Notes",
                    "Translation completed with ambiguity notes:\n\n" + note_text,
                )
        except Exception as exc:
            dialogs.Messagebox.show_error(
                "Translation Error", f"Failed to apply translation: {exc}"
            )
        finally:
            self.root.config(cursor="")

    def translate_with_ai(self, selected_only=False):
        """
        Translates selected text or full document using AI while preserving Markdown formatting.

        :param bool selected_only: True to translate selection only, False for full document.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            dialogs.Messagebox.show_info(
                "No document", "Please open or create a document first."
            )
            return

        if self.translation_job_active:
            dialogs.Messagebox.show_info(
                "Translation In Progress",
                "Please wait for the current translation to finish before starting another one.",
            )
            return

        source_lang, target_lang = self._prompt_translation_languages()
        if not source_lang or not target_lang:
            return

        if source_lang.strip().lower() == target_lang.strip().lower():
            dialogs.Messagebox.show_info(
                "Language Selection", "Source and target language are the same."
            )
            return

        start_idx, end_idx, source_text = self._get_translation_scope(
            text_area, selected_only
        )
        if source_text is None:
            return

        tab_index = self.notebook.index(self.notebook.select())
        translation_chunks = split_markdown_for_translation(source_text, chunk_lines=20)
        total_chunks = max(1, len(translation_chunks))
        session = self._prepare_translation_session(
            tab_index,
            text_area,
            start_idx,
            end_idx,
            source_text,
            total_chunks,
        )
        self.translation_job_active = True
        self.root.config(cursor="watch")

        def worker():
            try:
                ambiguity_notes = []
                for chunk_index, chunk_text in enumerate(translation_chunks, start=1):
                    if self._translation_cancel_requested:
                        raise RuntimeError("Translation cancelled by user.")
                    while True:
                        try:
                            translated_chunk, chunk_notes = translate_markdown_with_ai(
                                chunk_text,
                                source_lang,
                                target_lang,
                            )
                            if not translated_chunk.strip():
                                raise RuntimeError("AI returned empty translation.")
                            ambiguity_notes.extend(chunk_notes)
                            self.root.after(
                                0,
                                lambda chunk=translated_chunk, index=chunk_index: self._append_translation_chunk(
                                    session,
                                    chunk,
                                    index,
                                ),
                            )
                            break
                        except TranslationConfigError as exc:
                            dialog_result = self._request_translation_api_key(exc)
                            if not dialog_result:
                                raise RuntimeError("Translation cancelled because no API key was provided.") from exc
                            self._apply_ai_key_dialog_result(dialog_result, show_feedback=False)

                self.root.after(
                    0,
                    lambda: self._finish_translation_session(session, ambiguity_notes),
                )
            except Exception as exc:
                self.root.after(
                    0,
                    lambda error_text=str(exc): self._fail_translation_session(
                        session,
                        error_text,
                    ),
                )

        threading.Thread(target=worker, daemon=True).start()

    def set_ai_provider(self, provider_name):
        """Sets current AI provider for translation at runtime (internal helper)."""
        normalized = (provider_name or "").strip().lower()
        if normalized == "athropic":
            normalized = "anthropic"
        if normalized in ("openrouter", "openai", "anthropic"):
            self.ai_provider_var.set(normalized)
            set_current_ai_provider(normalized)

    def toggle_pdf_mode(self):
        """
        Toggles between PyMuPDF and Docling PDF conversion modes.
        """
        self.use_docling_pdf = self.pdf_mode_var.get()

    def show_pdf_converter_info(self):
        """
        Shows information about available PDF converters.
        """
        info_text = (
            "PDF Converter Information:\n\n"
            "1. PyMuPDF (Default)\n"
            "   - Speed: Very Fast\n"
            "   - Memory: Low\n"
            "   - Quality: Good for simple documents\n"
            "   - Best for: Text extraction, simple PDFs\n\n"
            "2. Docling (Advanced)\n"
            "   - Speed: Moderate (requires ML models)\n"
            "   - Memory: Higher\n"
            "   - Quality: Excellent for complex documents\n"
            "   - Best for: Academic papers, reports with tables\n"
            "   - Note: First use may take 2-5 seconds\n"
            "   - Install: pip install docling\n\n"
            "Current Mode: {}\n\n"
            "You can switch in Tools > Use Advanced PDF Conversion (Docling)"
        ).format("Docling (Advanced)" if self.use_docling_pdf else "PyMuPDF (Fast)")

        messagebox.showinfo("PDF Converter Information", info_text)

    def insert_table(self):
        """
        Inserts a table with customizable cell content at cursor position.
        """

        text_area = self.get_current_text_area()
        if not text_area:
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Table")
        dialog.transient(self.root)
        dialog.grab_set()

        text_color = "#E8E8E8"
        secondary_text_color = "#BDBDBD"
        input_bg_color = "#2A2A2A"
        input_fg_color = "#F5F5F5"

        # Configuration frame at top
        config_frame = tk.Frame(dialog, relief=tk.RAISED, borderwidth=1)
        config_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        tk.Label(
            config_frame,
            text="Rows (including header):",
            anchor="w",
            fg=text_color,
        ).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        rows_var = tk.IntVar(value=3)
        rows_spinbox = tk.Spinbox(
            config_frame,
            from_=2,
            to=20,
            textvariable=rows_var,
            width=10,
            bg=input_bg_color,
            fg=input_fg_color,
            insertbackground=input_fg_color,
            buttonbackground=input_bg_color,
        )
        rows_spinbox.grid(row=0, column=1, padx=5, pady=5)

        tk.Label(config_frame, text="Columns:", anchor="w", fg=text_color).grid(
            row=0, column=2, padx=5, pady=5, sticky="w"
        )
        cols_var = tk.IntVar(value=3)
        cols_spinbox = tk.Spinbox(
            config_frame,
            from_=2,
            to=10,
            textvariable=cols_var,
            width=10,
            bg=input_bg_color,
            fg=input_fg_color,
            insertbackground=input_fg_color,
            buttonbackground=input_bg_color,
        )
        cols_spinbox.grid(row=0, column=3, padx=5, pady=5)

        # Canvas frame for table grid
        canvas_frame = tk.Frame(dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(canvas_frame, borderwidth=0)
        scrollbar_v = tk.Scrollbar(
            canvas_frame, orient="vertical", command=canvas.yview
        )
        scrollbar_h = tk.Scrollbar(
            canvas_frame, orient="horizontal", command=canvas.xview
        )
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_v.pack(side="right", fill="y")
        scrollbar_h.pack(side="bottom", fill="x")

        # Store cell entries
        cell_entries = []

        def create_table_grid():
            """
            Creates or recreates the table grid based on current dimensions.
            """

            # Clear existing entries
            for widget in scrollable_frame.winfo_children():
                widget.destroy()
            cell_entries.clear()

            rows = rows_var.get()
            cols = cols_var.get()

            # Create grid of entry widgets
            for r in range(rows):
                row_entries = []
                for c in range(cols):
                    # Determine default content
                    if r == 0:
                        default_text = f"Header {c + 1}"
                    else:
                        default_text = f"Cell {r}-{c + 1}"

                    # Create entry with label
                    cell_frame = tk.Frame(
                        scrollable_frame, relief=tk.RIDGE, borderwidth=1
                    )
                    cell_frame.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")

                    label = tk.Label(
                        cell_frame,
                        text=f"[{r},{c}]",
                        font=("Arial", 8),
                        fg=secondary_text_color,
                    )
                    label.pack(anchor="nw", padx=2, pady=2)

                    entry = tk.Entry(
                        cell_frame,
                        width=15,
                        bg=input_bg_color,
                        fg=input_fg_color,
                        insertbackground=input_fg_color,
                    )
                    entry.insert(0, default_text)
                    entry.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)

                    row_entries.append(entry)

                cell_entries.append(row_entries)

            # Make columns expandable
            for c in range(cols):
                scrollable_frame.columnconfigure(c, weight=1)

        def update_table_grid(*args):
            """
            Updates the table grid when dimensions change.
            """

            create_table_grid()

        # Bind spinbox changes to update grid
        rows_var.trace_add("write", update_table_grid)
        cols_var.trace_add("write", update_table_grid)

        # Initial table grid
        create_table_grid()

        def insert_table_content():
            """
            Generates table markdown from entry widgets and updates the preview file.
            """

            rows = rows_var.get()
            cols = cols_var.get()
            table_lines = []

            # Header row
            header_values = [
                entry.get().strip() or f"Header {i + 1}"
                for i, entry in enumerate(cell_entries[0])
            ]
            header = "| " + " | ".join(header_values) + " |"
            table_lines.append(header)

            # Separator row
            separator = "| " + " | ".join(["---" for _ in range(cols)]) + " |"
            table_lines.append(separator)

            # Data rows
            for row_idx in range(1, rows):
                row_values = [
                    entry.get().strip() or f"Cell {row_idx}-{i + 1}"
                    for i, entry in enumerate(cell_entries[row_idx])
                ]
                data_row = "| " + " | ".join(row_values) + " |"
                table_lines.append(data_row)

            table_text = "\n" + "\n".join(table_lines) + "\n\n"

            # Insert at cursor position
            text_area.insert("insert", table_text)
            dialog.destroy()
            self.update_preview()

        # Button frame
        button_frame = tk.Frame(dialog)
        button_frame.pack(side=tk.BOTTOM, pady=10)

        ttkb.Button(
            button_frame,
            text="Insert Table",
            command=insert_table_content,
            width=15,
            bootstyle=(SUCCESS, OUTLINE),
        ).pack(side=tk.LEFT, padx=5)
        ttkb.Button(
            button_frame,
            text="Cancel",
            command=dialog.destroy,
            width=15,
            bootstyle=(SECONDARY, OUTLINE),
        ).pack(side=tk.LEFT, padx=5)

        # Set dialog size based on initial table dimensions
        width = min(800, 180 * cols_var.get() + 120)
        height = min(650, 80 * rows_var.get() + 200)
        dialog.geometry(f"{width}x{height}")

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        dialog.wait_window()

    def show_table_help(self):
        """
        Shows the help dialog for table syntax.
        """

        help_text = """📋 Markdown Table Syntax Guide

Basic Table Structure:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Header 1 | Header 2 | Header 3 |
|----------|----------|----------|
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

Column Alignment:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Left Align | Center Align | Right Align |
|:-----------|:------------:|------------:|
| Left       | Center       | Right       |
| Text       | Text         | Text        |

Alignment Syntax:
  • Left:    |:---|     (colon on left)
  • Center:  |:--:|     (colon on both sides)
  • Right:   |---:|     (colon on right)

Quick Tips:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Use | to separate columns
✓ Second row must be separator (- - -)
✓ Separators need at least 3 dashes
✓ Outer pipes | are optional but recommended
✓ Cell content width doesn't need to match
✓ Use Table menu → Insert Table for quick creation

Example - Data Table:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
| Name    | Age | Country |
|:--------|:---:|--------:|
| Alice   | 25  | USA     |
| Bob     | 30  | Canada  |
| Charlie | 28  | UK      |
"""
        messagebox.showinfo("Markdown Table Syntax Help", help_text)

    def export_to_html_dialog(self):
        """
        Shows dialog to export current the markdown document to HTML.
        """

        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return

        # Get current file path to suggest HTML filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]

        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.html"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.html"

        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".html",
            filetypes=[("HTML files", "*.html"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to HTML",
        )

        if output_path:
            export_to_html(self, output_path)

    def export_to_docx_dialog(self):
        """
        Shows the dialog to export the current markdown document to Word.
        """

        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return

        # Get current file path to suggest Word filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]

        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.docx"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.docx"

        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word documents", "*.docx"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to Word",
        )

        if output_path:
            export_to_docx(self, output_path)

    def export_to_pdf_dialog(self):
        """
        Shows the dialog to export the current markdown document to PDF.
        """

        if not self.editors:
            dialogs.Messagebox.show_info("Info", "No document to export.")
            return

        # Get current file path to suggest PDF filename
        idx = self.notebook.index(self.notebook.select())
        current_path = self.file_paths[idx]

        # Suggest filename
        if current_path:
            base_name = os.path.splitext(os.path.basename(current_path))[0]
            initial_dir = os.path.dirname(current_path)
            initial_file = f"{base_name}.pdf"
        else:
            initial_dir = os.path.expanduser("~")
            initial_file = "document.pdf"

        # Show save dialog
        output_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF documents", "*.pdf"), ("All files", "*.*")],
            initialdir=initial_dir,
            initialfile=initial_file,
            title="Export to PDF",
        )

        if not output_path:
            return

        # Take the content markdown now
        md_content = self.editors[idx].get("1.0", "end-1c")

        # Resolve the base directory so the exporter can inline local images.
        # We pass the raw filesystem path; pdf_exporter._inline_local_images()
        # handles the conversion to absolute paths and base64 data URIs, making
        # the resulting HTML fully self-contained for WeasyPrint.
        base_dir = None
        if current_path:
            base_dir = os.path.dirname(os.path.abspath(current_path))

        # Use markdown2 (same as the rest of the app) for consistent rendering.
        import markdown2 as _md2
        html_content = _md2.markdown(
            md_content,
            extras=["fenced-code-blocks", "code-friendly", "tables", "break-on-newline"],
        )

        # Export to PDF using WeasyPrint (images inlined as base64 inside the exporter)
        try:
            export_markdown_to_pdf(html_content, output_path, base_dir)
            dialogs.Messagebox.show_info(
                "Export Successful",
                f"PDF saved to:\n{output_path}",
            )
        except Exception as exc:
            import traceback
            dialogs.Messagebox.show_error(
                "PDF Export Failed",
                f"Could not export PDF:\n{exc}\n\nSee console for full traceback.",
            )
            traceback.print_exc()

    def show_help(self):
        """
        Displays a help dialog with information about the application features.
        
        Opens a new help window containing detailed descriptions of all application menus,
        menu items, and their functionality. The help window features organized sections
        for File, View, Edit, Settings, Tools, and Table menus with descriptions and
        keyboard shortcuts where applicable.

        :return: None. Opens a new window for display but does not return a value.
        """
        help_window = tk.Toplevel(self.root)
        help_window.title("Markdown Reader - Help")
        help_window.transient(self.root)
        help_window.resizable(False, False)

        screen_width = help_window.winfo_screenwidth()
        screen_height = help_window.winfo_screenheight()
        window_width = min(700, max(520, screen_width - 80))
        max_window_height = int(screen_height * 0.7)
        window_height = min(800, max(520, max_window_height))

        # Center the help window while keeping it fully inside the screen.
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (window_width // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - (window_height // 2)
        x = max(20, min(x, screen_width - window_width - 20))
        y = max(20, min(y, screen_height - window_height - 40))
        help_window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Colors
        bg_color = "#2A2A2A"
        text_color = "#F5F5F5"
        
        # Main container
        main_container = tk.Frame(help_window, bg=bg_color)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Help text area
        help_text = ScrolledText(
            main_container,
            height=35,
            width=75,
            wrap=tk.WORD,
            font=("Arial", 8),
            bg=bg_color,
            fg=text_color,
            insertbackground=text_color,
            relief=tk.FLAT,
            borderwidth=0
        )
        help_text.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Tags for formatting
        help_text.tag_configure("bold_item", font=("Arial", 8, "bold"), foreground=text_color)
        help_text.tag_configure("menu_header", font=("Arial", 9, "bold"), foreground=text_color,justify="left",spacing1=10,spacing3=10)
        
        # File Menu
        help_text.insert("end", "1. File Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "1.1 New", "bold_item")
        help_text.insert("end", "\n    Creates a new blank Markdown (.md) document for editing.\n\n")
        
        help_text.insert("end", "1.2 Open File", "bold_item")
        help_text.insert("end", "\n    Opens an existing Markdown (.md) file from your system for viewing or editing.\n\n")
        
        help_text.insert("end", "1.3 Save File", "bold_item")
        help_text.insert("end", "\n    Saves the current Markdown document to the selected file location.\n\n")
        
        help_text.insert("end", "1.4 Export to HTML", "bold_item")
        help_text.insert("end", "\n    Converts the current Markdown document into an HTML file for web viewing.\n\n")
        
        help_text.insert("end", "1.5 Export to Word", "bold_item")
        help_text.insert("end", "\n    Exports the current Markdown document as a Microsoft Word (.docx) file.\n\n")
        
        help_text.insert("end", "1.6 Export to PDF", "bold_item")
        help_text.insert("end", "\n    Generates a PDF version of the current Markdown document.\n\n")
        
        help_text.insert("end", "1.7 Close", "bold_item")
        help_text.insert("end", "\n    Closes the currently open Markdown document without exiting the application.\n\n")
        
        help_text.insert("end", "1.8 Close All", "bold_item")
        help_text.insert("end", "\n    Closes all open Markdown documents in the editor.\n\n")
        
        help_text.insert("end", "1.9 Exit", "bold_item")
        help_text.insert("end", "\n    Closes the application completely.\n\n")

        # View Menu
        help_text.insert("end", "2. View Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "2.1 Toggle Dark Mode", "bold_item")
        help_text.insert("end", "\n    Switches the interface between light and dark themes for improved readability.\n\n")
        
        help_text.insert("end", "2.2 Open Preview in Browser", "bold_item")
        help_text.insert("end", "\n    Opens the rendered Markdown preview in your default web browser.\n\n")

        help_text.insert("end", "2.3 Show AI Agent Panel", "bold_item")
        help_text.insert("end", "\n    Displays the AI agent interface for interacting with AI-powered features.\n\n")
        
        # Edit Menu
        help_text.insert("end", "3. Edit Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "3.1 Undo", "bold_item")
        help_text.insert("end", "\n    Reverts the most recent change made in the document.\n\n")
        
        help_text.insert("end", "3.2 Redo", "bold_item")
        help_text.insert("end", "\n    Restores the most recently undone change.\n\n")
        
        help_text.insert("end", "3.3 Translate with AI", "bold_item")
        help_text.insert("end", "\n    Uses AI to translate selected text into another language.\n\n")
        help_text.insert("end", "    3.3.1 Translate Selected Text with AI", "bold_item")
        help_text.insert("end", "\n        Translates only the selected portion of text using AI.\n\n")
        help_text.insert("end", "    3.3.2 Translate Full Document with AI", "bold_item")
        help_text.insert("end", "\n        Translates the entire document using AI.\n\n")
        
        # Settings Menu
        help_text.insert("end", "4. Settings Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "4.1 AI Provider & API Keys", "bold_item")
        help_text.insert("end", "\n    Configures AI service providers and API keys used for AI-powered features.\n\n")
        
        # Tools Menu
        help_text.insert("end", "5. Tools Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "5.1 Use Advanced PDF Conversion (Docling)", "bold_item")
        help_text.insert("end", "\n    Enables enhanced PDF generation using the Docling conversion engine.\n\n")
        
        help_text.insert("end", "5.2 PDF Converter Info", "bold_item")
        help_text.insert("end", "\n    Displays information about the PDF conversion engine used by the application.\n\n")
        
        # Table Menu
        help_text.insert("end", "6. Table Menu", "menu_header")
        help_text.insert("end", "\n")
        
        help_text.insert("end", "6.1 Insert Table", "bold_item")
        help_text.insert("end", "\n    Provide column names and data in the predefined table format to insert a Markdown-formatted table into the document.\n\n")
        
        help_text.insert("end", "6.2 Table Syntax Help", "bold_item")
        help_text.insert("end", "\n    Provides guidance on writing and formatting tables using Markdown syntax.")
        
        help_text.config(state=tk.DISABLED)

