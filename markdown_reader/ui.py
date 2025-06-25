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

        # --- Toolbar state ---
        self.current_font_family = "Consolas"
        self.current_font_size = 14
        self.current_fg_color = "#000000"
        self.current_bg_color = "#ffffff"

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

        # --- Toolbar ---
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED, bg="#f7f9fa")
        # Style dropdown
        self.style_var = tk.StringVar(value="Normal text")
        style_options = ["Normal text", "Heading 1", "Heading 2", "Heading 3"]
        style_menu = tk.OptionMenu(toolbar, self.style_var, *style_options, command=self.apply_style)
        style_menu.config(width=12)
        style_menu.pack(side=tk.LEFT, padx=2, pady=2)
        # Font family dropdown
        import tkinter.font
        fonts = sorted(set(tkinter.font.families()))
        self.font_var = tk.StringVar(value="Consolas")
        font_menu = tk.OptionMenu(toolbar, self.font_var, *fonts, command=self.apply_font)
        font_menu.config(width=10)
        font_menu.pack(side=tk.LEFT, padx=2)
        # Font size
        self.font_size_var = tk.IntVar(value=14)
        tk.Button(toolbar, text="-", command=lambda: self.change_font_size(-1)).pack(side=tk.LEFT, padx=1)
        tk.Entry(toolbar, textvariable=self.font_size_var, width=3, justify='center').pack(side=tk.LEFT)
        tk.Button(toolbar, text="+", command=lambda: self.change_font_size(1)).pack(side=tk.LEFT, padx=1)
        # Bold, Italic, Underline
        tk.Button(toolbar, text="B", font=("Arial", 10, "bold"), command=self.toggle_bold).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="I", font=("Arial", 10, "italic"), command=self.toggle_italic).pack(side=tk.LEFT, padx=2)
        tk.Button(toolbar, text="U", font=("Arial", 10, "underline"), command=self.toggle_underline).pack(side=tk.LEFT, padx=2)
        # Text color
        tk.Button(toolbar, text="A", command=self.choose_fg_color).pack(side=tk.LEFT, padx=2)
        # Highlight color
        tk.Button(toolbar, text="\u0332", font=("Arial", 10), command=self.choose_bg_color).pack(side=tk.LEFT, padx=2)
        toolbar.pack(fill=tk.X)

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
        base_font = (self.current_font_family, self.current_font_size)
        text_area = self.get_current_text_area()
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
            abs_path = os.path.abspath(file_path)
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
        abs_path = os.path.abspath(path)
        idx = self.notebook.index(self.notebook.select())
        text_area = self.get_current_text_area()

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
        self.update_preview()

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"

        for text_area in self.editors:
            text_area.config(bg=bg, fg=fg, insertbackground=fg)

    def highlight_markdown(self):
        # Get the current editor
        text_area = self.get_current_text_area()
        content = text_area.get("1.0", tk.END)

        # Remove all previous tags
        for tag in text_area.tag_names():
            text_area.tag_remove(tag, "1.0", tk.END)

        # Use the selected font for highlighting
        import tkinter.font
        font_name = getattr(self, 'current_font_family', 'Consolas')
        font_size = getattr(self, 'current_font_size', 14)
        text_area.tag_configure("heading", foreground="#333333", font=(font_name, font_size + 4, "bold"))
        text_area.tag_configure("bold", font=(font_name, font_size, "bold"))
        text_area.tag_configure("italic", font=(font_name, font_size, "italic"))
        text_area.tag_configure("code", foreground="#d19a66", background="#f6f8fa", font=(font_name, font_size))
        text_area.tag_configure("link", foreground="#2aa198", underline=True)
        text_area.tag_configure("blockquote", foreground="#6a737d", font=(font_name, font_size, "italic"))
        text_area.tag_configure("list", foreground="#b58900", font=(font_name, font_size, "bold"))

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
            for m in re.finditer(r"(?<!\*)\*(?!\*)([^*]+)(?<!\*)\*(?!\*)|(?<!_)_(?!_)([^_]+)(?<!_)_(?!\*)", line):
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

    def quit(self):
        if self.observer:
            self.observer.stop()
            self.observer.join()
        self.root.quit()

    def save_file(self):
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

    # --- Toolbar functions ---
    def get_current_text_area(self):
        if not self.editors:
            return None
        idx = self.notebook.index(self.notebook.select())
        return self.editors[idx]

    def apply_style(self, style):
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
        start_line = int(sel_start.split('.')[0])
        end_line = int(sel_end.split('.')[0])
        for line in range(start_line, end_line + 1):
            line_start = f"{line}.0"
            line_end = f"{line}.end"
            line_text = text_area.get(line_start, line_end)
            # Remove existing heading marks
            new_text = line_text.lstrip('# ').lstrip()
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
        new_size = max(6, self.font_size_var.get() + delta)
        self.font_size_var.set(new_size)
        self.apply_font(self.font_var.get())
        self.current_font_size = new_size
        self.update_preview()

    def toggle_bold(self):
        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already bold, remove **, else add **
            if selected_text.startswith("**") and selected_text.endswith("**") and len(selected_text) > 4:
                new_text = selected_text[2:-2]
            else:
                new_text = f"**{selected_text}**"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            from tkinter import messagebox
            messagebox.showinfo("No selection", "Please select text to make bold.")
            return
        self.update_preview()

    def toggle_italic(self):
        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # If already italic, remove *, else add * (single asterisk)
            if (selected_text.startswith("*") and selected_text.endswith("*") and len(selected_text) > 2) or \
               (selected_text.startswith("_") and selected_text.endswith("_") and len(selected_text) > 2):
                new_text = selected_text[1:-1]
            else:
                new_text = f"*{selected_text}*"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            from tkinter import messagebox
            messagebox.showinfo("No selection", "Please select text to make italic.")
            return
        self.update_preview()

    def toggle_underline(self):
        text_area = self.get_current_text_area()
        if not text_area:
            return
        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)
            # Use HTML <u> for underline in Markdown (not standard, but works in many renderers)
            if selected_text.startswith("<u>") and selected_text.endswith("</u>") and len(selected_text) > 7:
                new_text = selected_text[3:-4]
            else:
                new_text = f"<u>{selected_text}</u>"
            text_area.delete(sel_start, sel_end)
            text_area.insert(sel_start, new_text)
        except tk.TclError:
            from tkinter import messagebox
            messagebox.showinfo("No selection", "Please select text to underline.")
            return
        self.update_preview()

    def choose_fg_color(self):
        from tkinter.colorchooser import askcolor
        text_area = self.get_current_text_area()
        if not text_area:
            return
        color = askcolor()[1]
        if color:
            try:
                sel_start = text_area.index("sel.first")
                sel_end = text_area.index("sel.last")
                selected_text = text_area.get(sel_start, sel_end)

                if selected_text.startswith('<span style="color:') and selected_text.endswith('</span>'):
                    return

                new_text = f'<span style="color:{color}">{selected_text}</span>'

                text_area.delete(sel_start, sel_end)
                text_area.insert(sel_start, new_text)

                self.current_fg_color = color
                self.update_preview()
            except tk.TclError:
                from tkinter import messagebox
                messagebox.showinfo("No selection", "Please select text to color.")

    def choose_bg_color(self):
        from tkinter.colorchooser import askcolor
        text_area = self.get_current_text_area()
        if not text_area:
            return
        color = askcolor()[1]
        if color:
            text_area.config(bg=color)
            self.current_bg_color = color
            self.update_preview()

    def update_preview(self):
        from markdown_reader.logic import update_preview
        text_area = self.get_current_text_area()
        if not text_area:
            return

        content = text_area.get("1.0", "end-1c")

        spans = []

        for tag in text_area.tag_names():
            if tag == "fgcolor":
                ranges = text_area.tag_ranges(tag)
                color = text_area.tag_cget(tag, "foreground")
                for i in range(0, len(ranges), 2):
                    start = text_area.index(ranges[i])
                    end = text_area.index(ranges[i + 1])
                    start_idx = text_area.count("1.0", start, "chars")[0]
                    end_idx = text_area.count("1.0", end, "chars")[0]
                    spans.append((start_idx, end_idx, color))

        spans.sort(reverse=True, key=lambda x: x[0])
#        for start_idx, end_idx, color in spans:
#            span_text = (
#                f'<span style="color:{color}">'
#                + content[start_idx:end_idx]
#                + '</span>\n\n'
#            )
#            content = content[:start_idx] + span_text + content[end_idx:]

        self._preview_content_override = content
        update_preview(self)
        self._preview_content_override = None
