import tkinter as tk
from markdown_reader.ui import MarkdownReader
import sys
import os
import traceback
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


def handle_open_file(event):
    """
    Handles file open events from macOS.

    :param event event: The open file event from macOS. 
    """
    
    file_path = event
    if os.path.isfile(file_path) and file_path.lower().endswith(('.md', '.markdown', '.html', '.htm', '.pdf')):
        app.load_file(file_path)


if __name__ == "__main__":
    def _log_unhandled_exception(exc_type, exc_value, exc_tb):
        try:
            log_path = os.path.expanduser("~/Library/Logs/MarkdownReader-launch.log")
            with open(log_path, "a", encoding="utf-8") as log_file:
                log_file.write("\n=== Unhandled Exception ===\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=log_file)
        except Exception:
            pass
        traceback.print_exception(exc_type, exc_value, exc_tb)

    sys.excepthook = _log_unhandled_exception

    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        
        # Apply ttkbootstrap theme to TkinterDnD window
        app_style = ttkb.Style(theme="darkly")
        
        print("TkinterDnD enabled - Drag and drop support available")
    except (ImportError, RuntimeError) as e:
        print(f"   Warning: tkinterdnd2 not available, drag-and-drop will be disabled")
        print(f"   Error: {e}")
        root = ttkb.Window(themename="darkly")
    
    # Ensure window is resizable
    root.resizable(width=True, height=True)

    app = MarkdownReader(root)
    
    # Handle file open events from macOS Finder
    root.createcommand(
        "::tk::mac::OpenDocument",
        lambda *args: handle_open_file(args[0]) if args else None,
    )

    # Handle file opening from command line
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            # Skip macOS system parameters (process serial number)
            if arg.startswith('-psn'):
                continue
            # Convert to absolute path
            file_path = os.path.abspath(arg)
            if os.path.isfile(file_path) and file_path.lower().endswith(('.md', '.markdown', '.html', '.htm', '.pdf')):
                app.load_file(file_path)
                break  # Only open the first file

    root.mainloop()