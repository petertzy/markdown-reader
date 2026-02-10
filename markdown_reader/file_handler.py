import os
from tkinter import messagebox

def load_file(path, app):
    """
    Deprecated: Use app.load_file() instead.
    This function is kept for backward compatibility only.
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
    Handle dropped files (Markdown or HTML).
    HTML files are automatically converted to Markdown.
    
    Supports multiple formats of event.data:
    - Single file: "path/to/file.md"
    - Quoted: "{/path/to/file.md}"
    - Multiple files (space-separated)
    - macOS format
    """
    try:
        # Parse the event data - handle various formats
        raw_data = str(event.data)
        
        print(f"🔍 Parsing drop data: {raw_data[:100]}")
        
        # Remove curly braces if present (common in tkinterdnd2)
        raw_data = raw_data.strip('{}')
        
        # Split by whitespace to handle multiple files
        # But be careful with paths that have spaces
        file_paths = []
        
        if '{' in raw_data or '}' in raw_data:
            # macOS format might use braces for each file
            import re
            paths = re.findall(r'\{([^}]+)\}', raw_data)
            file_paths = paths if paths else [raw_data]
        else:
            # Try to split by common path separators
            # This is a simplified approach - works for most cases
            file_paths = [raw_data]
        
        print(f"   Extracted {len(file_paths)} file path(s)")
        
        # Process each file
        processed = False
        for file_path in file_paths:
            file_path = file_path.strip()
            if not file_path:
                continue
            
            print(f"   Processing: {file_path}")
            
            # Check if file exists
            if not os.path.isfile(file_path):
                print(f"   ⚠️  File not found: {file_path}")
                continue
            
            # Check file extension
            if not file_path.lower().endswith(('.md', '.markdown', '.html', '.htm')):
                print(f"   ⚠️  Unsupported file type: {file_path}")
                messagebox.showwarning("Warning", f"Only .md and .html files are supported")
                continue
            
            # Create a new tab and load the file
            print(f"   ✅ Loading file: {file_path}")
            app.new_file()
            idx = app.notebook.index(app.notebook.select())
            
            # Use app.load_file() which handles HTML to Markdown conversion
            app.load_file(file_path)
            processed = True
            
            # Only process the first valid file
            break
        
        if not processed:
            messagebox.showwarning("Warning", "No valid files found in drop data")
            
    except Exception as e:
        print(f"❌ Error in drop_file: {e}")
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to process dropped file: {e}")


