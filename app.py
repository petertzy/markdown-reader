import tkinter as tk
from markdown_reader.ui import MarkdownReader
import sys
import os
import ttkbootstrap as ttkb
from ttkbootstrap.constants import *


def handle_open_file(event):
    """Handle file open events from macOS"""
    file_path = event
    if os.path.isfile(file_path) and file_path.lower().endswith(('.md', '.markdown')):
        app.load_file(file_path)

if __name__ == "__main__":
    try:
        from tkinterdnd2 import TkinterDnD
        root = TkinterDnD.Tk()
        
        # Apply ttkbootstrap theme to TkinterDnD window
        app_style = ttkb.Style(theme="darkly")
        
        print("TkinterDnD enabled - Drag and drop support available")
    except ImportError as e:
        print(f"   Warning: tkinterdnd2 not installed, drag-and-drop will be disabled")
        print(f"   Error: {e}")
        root = ttkb.Window(themename="darkly")

    app = MarkdownReader(root)
    
    # Handle file open events from macOS Finder
    root.createcommand("::tk::mac::OpenDocument", lambda *args: handle_open_file(args[0]))

    # Handle file opening from command line
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            # Skip macOS system parameters (process serial number)
            if arg.startswith('-psn'):
                continue
            # Convert to absolute path
            file_path = os.path.abspath(arg)
            if os.path.isfile(file_path) and file_path.lower().endswith(('.md', '.markdown')):
                app.load_file(file_path)
                break  # Only open the first file

    root.mainloop()
