import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
import markdown2
import webbrowser
import os

class MarkdownReader:
    def __init__(self, root):
        self.root = root
        self.root.title("Markdown Reader")
        self.root.geometry("900x600")
        self.dark_mode = False
        self.preview_file = "preview.html"

        self.create_widgets()
        self.bind_events()

    def create_widgets(self):
        # 建立選單
        menubar = tk.Menu(self.root)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="打開檔案", command=self.open_file)
        filemenu.add_separator()
        filemenu.add_command(label="退出", command=self.root.quit)
        menubar.add_cascade(label="檔案", menu=filemenu)

        viewmenu = tk.Menu(menubar, tearoff=0)
        viewmenu.add_command(label="切換黑暗模式", command=self.toggle_dark_mode)
        menubar.add_cascade(label="檢視", menu=viewmenu)

        self.root.config(menu=menubar)

        # 編輯區
        self.text_area = ScrolledText(self.root, wrap=tk.WORD, font=("Helvetica", 12))
        self.text_area.pack(fill=tk.BOTH, expand=True)
        self.text_area.bind("<<Modified>>", self.on_text_change)

    def bind_events(self):
        # 拖放支援（僅限 Windows/macOS）
        self.root.drop_target_register('DND_Files')
        self.root.dnd_bind('<<Drop>>', self.drop_file)

    def drop_file(self, event):
        file_path = event.data.strip('{}')  # 去除外層大括號（Windows格式）
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
            messagebox.showerror("錯誤", f"無法讀取檔案：{e}")

    def on_text_change(self, event):
        self.text_area.edit_modified(False)
        self.update_preview()

    def update_preview(self):
        markdown_text = self.text_area.get('1.0', tk.END)
        html_content = markdown2.markdown(
            markdown_text,
            extras=["fenced-code-blocks", "code-friendly", "tables"]  # ✅ 加入 tables 支援
        )

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
        # ✅ 只打開一次瀏覽器
        if not hasattr(self, 'browser_opened') or not self.browser_opened:
            webbrowser.open(f"file://{os.path.abspath(self.preview_file)}", new=0)
            self.browser_opened = True

    def toggle_dark_mode(self):
        self.dark_mode = not self.dark_mode
        bg = "#1e1e1e" if self.dark_mode else "white"
        fg = "#dcdcdc" if self.dark_mode else "black"
        self.text_area.config(bg=bg, fg=fg, insertbackground=fg)
        self.update_preview()

if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()  # 正確使用 TkinterDnD.Tk()
    except ImportError:
        print("提示：如需拖放支援，請安裝 tkinterdnd2（pip install tkinterdnd2）")
        root = tk.Tk()

    app = MarkdownReader(root)
    root.mainloop()

