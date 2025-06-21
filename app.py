import tkinter as tk
from markdown_reader.ui import MarkdownReader

if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
    except ImportError:
        print("Note: tkinterdnd2 not installed, drag-and-drop will be disabled")
        root = tk.Tk()

    app = MarkdownReader(root)

    import sys, os
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if file_path.lower().endswith(('.md', '.markdown', '.MD', '.MARKDOWN')) and os.path.isfile(file_path):
            app.load_file(file_path)

    root.mainloop()
