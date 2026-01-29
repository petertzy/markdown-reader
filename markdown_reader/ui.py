import os
import re
import threading
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from markdown_reader.logic import update_preview
from markdown_reader.logic import open_preview_in_browser
from markdown_reader.logic import export_to_html
from markdown_reader.logic import export_to_docx
from markdown_reader.logic import convert_html_to_markdown
from markdown_reader.file_handler import load_file, drop_file
from markdown_reader.utils import get_preview_file
import tkinter.font  # moved here from inside methods

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
        
        # Track which tabs have unsaved modifications
        self.modified_tabs = set()
        
        # Flag to prevent marking as modified during file loading
        self._loading_file = False
        
        # Flag to prevent marking as modified right after saving
        self._just_saved = False

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New", command=self.new_file)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_command(label="Save File", command=self.save_file)
        filemenu.add_separator()
        filemenu.add_command(label="Export to HTML", command=self.export_to_html_dialog)
        filemenu.add_command(label="Export to Word", command=self.export_to_docx_dialog)
        filemenu.add_separator()
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

        editmenu = tk.Menu(menubar, tearoff=0)
        editmenu.add_command(label="Undo", command=self.undo_action)
        editmenu.add_command(label="Redo", command=self.redo_action)
        menubar.add_cascade(label="Edit", menu=editmenu)

        # ADD THIS NEW BLOCK:
        tablemenu = tk.Menu(menubar, tearoff=0)
        tablemenu.add_command(label="Insert Table...", command=self.insert_table)
        tablemenu.add_separator()
        tablemenu.add_command(label="Table Syntax Help", command=self.show_table_help)
        menubar.add_cascade(label="Table", menu=tablemenu)
     
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
        # Insert table button
        tk.Button(toolbar, text="⊞", font=("Arial", 12), command=self.insert_table).pack(side=tk.LEFT, padx=2)
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
        self.root.bind_all("<Control-z>", lambda event: self.undo_action())
        self.root.bind_all("<Control-y>", lambda event: self.redo_action())
        self.root.bind_all("<Command-z>", lambda event: self.undo_action())
        self.root.bind_all("<Command-Shift-Z>", lambda event: self.redo_action())

    def new_file(self):
        frame = tk.Frame(self.notebook)
        base_font = (self.current_font_family, self.current_font_size)
        text_area = self.get_current_text_area()
        text_area = ScrolledText(frame, wrap=tk.WORD, font=base_font, undo=True)
        text_area.pack(fill=tk.BOTH, expand=True)
        text_area.bind("<<Modified>>", self.on_text_change)
        self.notebook.add(frame, text="Untitled")
        self.notebook.select(len(self.editors))
        self.editors.append(text_area)
        self.file_paths.append(None)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[
            ("Markdown files", "*.md *.MD"),
            ("HTML files", "*.html *.HTML *.htm *.HTM"),
            ("All files", "*.*")
        ])
        if file_path and (file_path.lower().endswith(".md") or file_path.lower().endswith((".html", ".htm"))):
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
        abs_path = os.path.abspath(path)
        idx = self.notebook.index(self.notebook.select())
        text_area = self.get_current_text_area()
        is_html = abs_path.lower().endswith((".html", ".htm"))

        try:
            # Set loading flag to prevent marking as modified
            self._loading_file = True
            
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
            if is_html:
                # Update tab name to show it's converted
                base_name = os.path.splitext(os.path.basename(abs_path))[0]
                self.notebook.tab(idx, text=f"{base_name}.md (converted)")
                # Don't set file_paths to HTML file - treat as new unsaved file
                self.file_paths[idx] = None
                self.current_file_path = None
            else:
                self.file_paths[idx] = abs_path
                self.notebook.tab(idx, text=os.path.basename(abs_path))
                self.current_file_path = abs_path
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load file: {e}")
        finally:
            # Always clear the loading flag first
            self._loading_file = False
            
            # Delay marking tab state to ensure all events are processed
            # Use after_idle to run after all pending events in the queue
            if is_html:
                # Mark as modified since it's converted content
                self.root.after(100, lambda: self.mark_tab_modified(idx))
            else:
                # Mark as saved since we just loaded from file
                self.root.after(100, lambda: self.mark_tab_saved(idx))

    def close_current_tab(self):
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

    def close_all_tabs(self):
        while self.editors:
            self.notebook.forget(0)
            del self.editors[0]
            del self.file_paths[0]
        # Clear modified tabs set
        self.modified_tabs.clear()

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
        
        # Don't mark as modified if we're loading a file or just saved
        if not self._loading_file and not self._just_saved:
            # Mark current tab as modified
            try:
                idx = self.notebook.index(self.notebook.select())
                self.mark_tab_modified(idx)
            except:
                pass
        
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
        # ADD THIS NEW LINE:
        text_area.tag_configure("table", foreground="#0066cc", font=(font_name, font_size))

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

    def mark_tab_modified(self, tab_index):
        """Mark a tab as having unsaved modifications"""
        if tab_index not in self.modified_tabs:
            self.modified_tabs.add(tab_index)
            # Get current tab title
            current_title = self.notebook.tab(tab_index, "text")
            # Add asterisk if not already present
            if not current_title.startswith("* "):
                self.notebook.tab(tab_index, text=f"* {current_title}")
    
    def mark_tab_saved(self, tab_index):
        """Mark a tab as saved (remove unsaved indicator)"""
        if tab_index in self.modified_tabs:
            self.modified_tabs.remove(tab_index)
        # Get current tab title and remove asterisk if present
        try:
            current_title = self.notebook.tab(tab_index, "text")
            if current_title.startswith("* "):
                self.notebook.tab(tab_index, text=current_title[2:])
        except:
            pass

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
                # Mark tab as saved
                self.mark_tab_saved(idx)
                # Set flag to ignore the next file change event
                self._just_saved = True
                # Clear flag after a short delay
                self.root.after(1000, lambda: setattr(self, '_just_saved', False))
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
                    # Mark tab as saved (will ensure no asterisk)
                    self.mark_tab_saved(idx)
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
        import re

        text_area = self.get_current_text_area()
        if not text_area:
            return
        color = askcolor()[1]
        if not color:
            return

        try:
            sel_start = text_area.index("sel.first")
            sel_end = text_area.index("sel.last")
            selected_text = text_area.get(sel_start, sel_end)

            if selected_text.strip() == "" or "\n" in selected_text:
                from tkinter import messagebox
                messagebox.showinfo("Tip", "Please select single-line non-empty text to set color.")
                return

            cleaned_text = re.sub(
                r'<span style="color:[^">]+?">(.*?)</span>', r'\1', selected_text, flags=re.DOTALL
            )
            new_text = f'<span style="color:{color}">{cleaned_text}</span>'

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
        if not self.current_file_path:
            return
        text_area = self.get_current_text_area()
        if not text_area:
            return
        update_preview(self)

    def undo_action(self):
        text_area = self.get_current_text_area()
        if text_area and text_area.edit_modified():
            try:
                text_area.edit_undo()
            except tk.TclError:
                pass

    def redo_action(self):
        text_area = self.get_current_text_area()
        if text_area:
            try:
                text_area.edit_redo()
            except tk.TclError:
                pass

    def insert_table(self):
        """Insert a table with customizable cell content at cursor position"""
        text_area = self.get_current_text_area()
        if not text_area:
            return
    
        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Insert Table")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Configuration frame at top
        config_frame = tk.Frame(dialog, relief=tk.RAISED, borderwidth=1)
        config_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        tk.Label(config_frame, text="Rows (including header):", anchor="w").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        rows_var = tk.IntVar(value=3)
        rows_spinbox = tk.Spinbox(config_frame, from_=2, to=20, textvariable=rows_var, width=10)
        rows_spinbox.grid(row=0, column=1, padx=5, pady=5)
    
        tk.Label(config_frame, text="Columns:", anchor="w").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        cols_var = tk.IntVar(value=3)
        cols_spinbox = tk.Spinbox(config_frame, from_=2, to=10, textvariable=cols_var, width=10)
        cols_spinbox.grid(row=0, column=3, padx=5, pady=5)
        
        # Canvas frame for table grid
        canvas_frame = tk.Frame(dialog)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        canvas = tk.Canvas(canvas_frame, borderwidth=0)
        scrollbar_v = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollbar_h = tk.Scrollbar(canvas_frame, orient="horizontal", command=canvas.xview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar_v.set, xscrollcommand=scrollbar_h.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar_v.pack(side="right", fill="y")
        scrollbar_h.pack(side="bottom", fill="x")
        
        # Store cell entries
        cell_entries = []
        
        def create_table_grid():
            """Create or recreate the table grid based on current dimensions"""
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
                        default_text = f"Header {c+1}"
                    else:
                        default_text = f"Cell {r}-{c+1}"
                    
                    # Create entry with label
                    cell_frame = tk.Frame(scrollable_frame, relief=tk.RIDGE, borderwidth=1)
                    cell_frame.grid(row=r, column=c, padx=2, pady=2, sticky="nsew")
                    
                    label = tk.Label(cell_frame, text=f"[{r},{c}]", font=("Arial", 8), fg="gray")
                    label.pack(anchor="nw", padx=2, pady=2)
                    
                    entry = tk.Entry(cell_frame, width=15)
                    entry.insert(0, default_text)
                    entry.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
                    
                    row_entries.append(entry)
                
                cell_entries.append(row_entries)
            
            # Make columns expandable
            for c in range(cols):
                scrollable_frame.columnconfigure(c, weight=1)
        
        def update_table_grid(*args):
            """Update table grid when dimensions change"""
            create_table_grid()
        
        # Bind spinbox changes to update grid
        rows_var.trace_add("write", update_table_grid)
        cols_var.trace_add("write", update_table_grid)
        
        # Initial table grid
        create_table_grid()
        
        def insert_table_content():
            """Generate table markdown from entry widgets"""
            rows = rows_var.get()
            cols = cols_var.get()
            table_lines = []
            
            # Header row
            header_values = [entry.get().strip() or f"Header {i+1}" for i, entry in enumerate(cell_entries[0])]
            header = "| " + " | ".join(header_values) + " |"
            table_lines.append(header)
            
            # Separator row
            separator = "| " + " | ".join(["---" for _ in range(cols)]) + " |"
            table_lines.append(separator)
            
            # Data rows
            for row_idx in range(1, rows):
                row_values = [entry.get().strip() or f"Cell {row_idx}-{i+1}" for i, entry in enumerate(cell_entries[row_idx])]
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
        
        tk.Button(button_frame, text="Insert Table", command=insert_table_content, width=15, height=1, bg="#4CAF50", fg="black").pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="Cancel", command=dialog.destroy, width=15, height=1).pack(side=tk.LEFT, padx=5)
        
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
        """Show help dialog for table syntax"""
        help_text = """Markdown Table Syntax:

| Header 1 | Header 2 | Header 3 |
| -------- | -------- | -------- |
| Cell 1   | Cell 2   | Cell 3   |
| Cell 4   | Cell 5   | Cell 6   |

Tips:
• Use | to separate columns
• Use --- in the separator row
• Alignment:
  - Left:   | :--- |
  - Center: | :---: |
  - Right:  | ---: |

Example with alignment:
| Left | Center | Right |
| :--- | :----: | ----: |
| A    | B      | C     |
"""
        messagebox.showinfo("Table Syntax Help", help_text)

    def export_to_html_dialog(self):
        """Show dialog to export current markdown document to HTML"""
        if not self.editors:
            messagebox.showinfo("Info", "No document to export.")
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
            title="Export to HTML"
        )
        
        if output_path:
            export_to_html(self, output_path)

    def export_to_docx_dialog(self):
        """Show dialog to export current markdown document to Word"""
        if not self.editors:
            messagebox.showinfo("Info", "No document to export.")
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
            title="Export to Word"
        )
        
        if output_path:
            export_to_docx(self, output_path)