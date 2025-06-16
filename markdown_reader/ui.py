import os
import re
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from markdown_reader.logic import update_preview, open_preview_in_browser
from markdown_reader.file_handler import load_file, drop_file
from markdown_reader.utils import get_preview_file

class MarkdownReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("1280x795")
        self.dark_mode = False
        self.preview_file = get_preview_file()
        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewmenu.add_command(label="Open Preview in Browser", command=lambda: open_preview_in_browser(self.preview_file))
        menubar.add_cascade(label="View", menu=viewmenu)

        self.root.config(menu=menubar)

        base_font = ("Consolas", 28)
        self.text_area = ScrolledText(self.root, wrap=tk.WORD, font=base_font)
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.bind("<<Modified>>", self.on_text_change)

    def bind_events(self):
        try:
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', lambda event: drop_file(event, self))
        except Exception:
            pass

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Markdown files", "*.md")])
        if file_path:
            load_file(file_path, self)

    def load_file(self, path):
        load_file(path, self)

    def on_text_change(self, event):
        self.text_area.edit_modified(False)
        self.highlight_markdown()
        update_preview(self)

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"
        self.text_area.config(bg=bg, fg=fg, insertbackground=fg)
        update_preview(self)
