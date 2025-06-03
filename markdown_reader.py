import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import markdown2
import webbrowser
import os
import sys

# Get resource path for use with bundled apps (e.g., py2app)
def get_resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    elif getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

class MarkdownReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("900x600")
        self.dark_mode = False
        self.preview_file = os.path.join(os.path.expanduser("~"), "preview.html")  # Use home directory to avoid read-only issues

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        # Menu
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="Open File", command=self.open_file)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="Toggle Dark Mode", command=self.toggle_dark_mode)
        menubar.add_cascade(label="View", menu=viewmenu)

        self.root.config(menu=menubar)

        # Text area
        self.text_area = ScrolledText(self.root, wrap=tk.WORD, font=("Helvetica", 12))
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.bind("<<Modified>>", self.on_text_change)

    def bind_events(self):
        try:
            self.root.drop_target_register('DND_Files')
            self.root.dnd_bind('<<Drop>>', self.drop_file)
        except Exception:
            pass  # If not in tkinterdnd2 environment, skip drag and drop

    def drop_file(self, event):
        file_path = event.data.strip('{}')  # Remove braces (macOS format)
        if file_path.endswith('.md'):
            self.load_file(file_path)

    def open_file(self):
        file_path = filedialog.askopenfilename(filetypes=[("Markdown files", "*.md")])
        if file_path:
            self.load_file(file_path)

    def load_file(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_area.delete('1.0', tk.END)
            self.text_area.insert(tk.END, content)
            self.update_preview()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")

    def on_text_change(self, event):
        self.text_area.edit_modified(False)
        self.update_preview()

    def update_preview(self):
        markdown_text = self.text_area.get('1.0', tk.END)
        html_content = markdown2.markdown(
            markdown_text,
            extras=["fenced-code-blocks", "code-friendly", "tables"]
        )

        try:
            with open(self.preview_file, 'w', encoding='utf-8') as f:
                f.write(f"""
                <html>
                <head>
                    <meta charset="UTF-8">
                    <style>
                        body {{
                            background-color: {'#1e1e1e' if self.dark_mode else 'white'};
                            color: {'#dcdcdc' if self.dark_mode else 'black'};
                            font-family: sans-serif;
                            padding: 20px;
                            font-size: 32px;
                            line-height: 1.6;
                        }}
                        pre, code {{
                            font-size: 28px;
                            white-space: pre-wrap;
                        }}
                        table {{
                            border-collapse: collapse;
                            width: 100%;
                            margin-top: 20px;
                        }}
                        th, td {{
                            text-align: left;
                            border: 1px solid #ccc;
                            padding: 12px 16px;
                            vertical-align: top;
                        }}
                        th {{
                            background-color: #f3f3f3;
                            color: #333;
                        }}
                        tr:nth-child(even) {{
                            background-color: #fafafa;
                        }}
                    </style>
                </head>
                <body>
                    {html_content}
                </body>
                </html>
                """)
            if not hasattr(self, 'browser_opened') or not self.browser_opened:
                webbrowser.open(f"file://{os.path.abspath(self.preview_file)}", new=0)
                self.browser_opened = True
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate HTML preview: {e}")

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"
        self.text_area.config(bg=bg, fg=fg, insertbackground=fg)
        self.update_preview()

if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        print("Note: tkinterdnd2 not installed, drag-and-drop will be disabled")
        root = tk.Tk()

    app = MarkdownReader(root)

    # If opened via double-clicking a .md file, sys.argv[1] will be the path
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if file_path.lower().endswith(('.md', '.markdown')) and os.path.isfile(file_path):
            app.load_file(file_path)
    root.mainloop()
