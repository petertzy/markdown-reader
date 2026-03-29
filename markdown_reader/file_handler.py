import os
import re
from tkinter import messagebox


def load_file(path, app):
    """
    Deprecated: Use app.load_file() instead.
    This function is kept for backward compatibility only.

    :raises RuntimeError: If the file does not load correctly.
    """
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        idx = app.notebook.index(app.notebook.select())
        text_area = app.editors[idx]
        text_area.delete('1.0', 'end')
        text_area.insert('end', content)
        app.current_file_path = path
        from markdown_reader.logic import update_preview
        update_preview(app)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load file: {e}")


def drop_file(event, app):
    """
    Handles dropped files (Markdown or HTML).
    - HTML files are automatically converted to Markdown.
    
    Supports multiple formats of event.data:
    - Single file: "path/to/file.md".
    - Quoted: "{/path/to/file.md}".
    - Multiple files (space-separated).
    - macOS format.

    :param event event: The drop file event. Child event.data can be of multiple formats (as above).
    :param MarkdownReader app: The MarkdownReader application instance.

    :raises RuntimeError: If the dropped file cannot be processed correctly.
    """

    try:
        raw_data = str(getattr(event, "data", "") or "").strip()
        if not raw_data:
            messagebox.showwarning("Warning", "No files were dropped")
            return

        splitlist = None
        tk_app = getattr(getattr(app, "root", None), "tk", None)
        if tk_app is not None and hasattr(tk_app, "splitlist"):
            splitlist = tk_app.splitlist

        file_paths = _extract_paths_from_drop_data(raw_data, splitlist)

        # Process each file
        processed_count = 0
        skipped_count = 0
        for file_path in file_paths:
            file_path = os.path.abspath(file_path.strip())
            if not file_path:
                continue

            # Check if file exists
            if not os.path.isfile(file_path):
                print(f"Skipping missing dropped path: {file_path}")
                skipped_count += 1
                continue

            # Check file extension
            if not file_path.lower().endswith(('.md', '.markdown', '.html', '.htm', '.pdf')):
                print(f"Skipping unsupported dropped file type: {file_path}")
                skipped_count += 1
                continue

            # Create a new tab and load the file
            app.new_file()

            # Use app.load_file() which handles HTML to Markdown conversion
            app.load_file(file_path)
            processed_count += 1

        if skipped_count > 0:
            messagebox.showwarning(
                "Warning",
                "Only .md, .markdown, .html, .htm, and .pdf files are supported",
            )

        if processed_count == 0:
            messagebox.showwarning("Warning", "No valid files found in drop data")

    except Exception as e:
        print(f"❌ Error in drop_file: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to process dropped file: {e}")


def _extract_paths_from_drop_data(raw_data, splitlist=None):
    """
    Extract one or more file-system paths from a TkDnD drop payload.

    :param str raw_data: The raw drop payload string received from the drag-and-drop event.
    :param callable splitlist: Optional Tk splitlist callable used to parse Tcl-style list payloads.

    :return: A list of parsed path strings. If parsing yields no tokens, returns a single-item list containing the original payload.

    :raises TypeError: If raw_data is not a string and cannot be processed by the regex fallback parser.
    """

    if callable(splitlist):
        try:
            parsed = [part.strip() for part in splitlist(raw_data) if str(part).strip()]
            if parsed:
                return parsed
        except Exception:
            pass

    # Fallback parser for raw payloads with braces, quotes, or plain whitespace.
    pattern = r"\{([^}]*)\}|\"([^\"]*)\"|(\S+)"
    matches = re.findall(pattern, raw_data)
    paths = []
    for brace_path, quoted_path, plain_path in matches:
        candidate = brace_path or quoted_path or plain_path
        candidate = candidate.strip()
        if candidate:
            paths.append(candidate)

    if paths:
        return paths

    return [raw_data]