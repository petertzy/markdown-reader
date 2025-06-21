from tkinter import messagebox

def load_file(path, app):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        app.text_area.delete('1.0', 'end')
        app.text_area.insert('end', content)
        app.current_file_path = path
        from markdown_reader.logic import update_preview
        update_preview(app)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load file: {e}")

def drop_file(event, app):
    file_path = event.data.strip('{}')
    if file_path.endswith('.md') or file_path.endswith('.MD'):
        load_file(file_path, app)

