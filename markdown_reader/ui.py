import os
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from markdown_reader.logic import open_preview_in_browser
from markdown_reader.file_handler import load_file, drop_file
from markdown_reader.utils import get_preview_file


class FileChangeHandler(FileSystemEventHandler):
    def __init__(self, app, filepath):
        self.app = app
        self.filepath = os.path.abspath(filepath)

    def on_modified(self, event):
        if os.path.abspath(event.src_path) == self.filepath:
            self.app.root.after(100, lambda: self.app.load_file(self.filepath))


class MarkdownReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("1280x795")
        self.dark_mode = False
        self.preview_file = get_preview_file()
        self.current_file_path = None
        self.observer = None

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_file)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_command(label="Save File", command=self.save_file)
        filemenu.add_command(label="Close", command=self.close_current_tab)
        filemenu.add_command(label="Close All", command=self.close_all_tabs)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        viewmenu.add_command(label="Open Preview in Browser",
                             command=lambda: open_preview_in_browser(self.preview_file, self))
        menubar.add_cascade(label="View", menu=viewmenu)

        self.root.config(menu=menubar)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.editors = []
        self.file_paths = []

        self.new_file()

    def bind_events(self):
        try:
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', lambda event: drop_file(event, self))
        except Exception:
            pass

        self.root.bind_all("<Control-s>", lambda event: self.save_file())
        self.root.bind_all("<Command-s>", lambda event: self.save_file())

    def new_file(self):
        frame = tk.Frame(self.notebook)
        base_font = ("Consolas", 28)
        text_area = ScrolledText(frame, wrap=tk.WORD, font=base_font)
        text_area.pack(fill=tk.BOTH, expand=True)
        text_area.bind("<<Modified>>", self.on_text_change)
        self.notebook.add(frame, text="Untitled")
        self.notebook.select(len(self.editors))
        self.editors.append(text_area)
        self.file_paths.append(None)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("Markdown files", "*.md *.MD"),
            ("All files", "*.*")
        ])
        if file_path and file_path.lower().endswith(".md"):
            self.new_file()
            self.load_file(file_path)
            self.start_watching(file_path)

    def load_file(self, path):
        abs_path = os.path.abspath(path)
        if not self.editors:
           self.new_file()
        idx = self.notebook.index(self.notebook.select())
        text_area = self.editors[idx]

        try:
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
            text_area.delete("1.0", tk.END)
            text_area.insert(tk.END, content)
            self.file_paths[idx] = abs_path
            self.notebook.tab(idx, text=os.path.basename(abs_path))
            self.current_file_path = abs_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")

    def close_current_tab(self):
        if not self.editors:
            return
        idx = self.notebook.index(self.notebook.select())
        self.notebook.forget(idx)
        del self.editors[idx]
        del self.file_paths[idx]

    def close_all_tabs(self):
        while self.editors:
            self.notebook.forget(0)
            del self.editors[0]
            del self.file_paths[0]

    def start_watching(self, path):
        if self.observer:
            self.observer.stop()
            self.observer.join()

        event_handler = FileChangeHandler(self, path)
        self.observer = Observer()
        watch_dir = os.path.dirname(os.path.abspath(path))
        self.observer.schedule(event_handler, path=watch_dir, recursive=False)
        self.observer.start()

    def on_text_change(self, event):
        widget = event.widget
        widget.edit_modified(False)
        self.highlight_markdown()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"

        for text_area in self.editors:
            text_area.config(bg=bg, fg=fg, insertbackground=fg)

    def highlight_markdown(self):
        pass

    def quit(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.root.quit()

    def save_file(self):
        idx = self.notebook.index(self.notebook.select())
        text_area = self.editors[idx]
        current_path = self.file_paths[idx]

        if current_path:
            try:
                content = text_area.get("1.0", "end-1c")
                with open(current_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save file: {e}")
        else:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".md",
                filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
                initialfile="default.md"
            )
            if file_path:
                try:
                    content = text_area.get("1.0", "end-1c")
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    self.file_paths[idx] = file_path
                    self.notebook.tab(idx, text=os.path.basename(file_path))
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to save file: {e}")
