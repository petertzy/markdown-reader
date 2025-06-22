import markdown2
import os
import webbrowser
from tkinter import messagebox

def update_preview(app):
    if not app.editors:
        return False
    try:
        idx = app.notebook.index(app.notebook.select())
        text_area = app.editors[idx]
        markdown_text = text_area.get("1.0", "end-1c")
        html_content = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "code-friendly", "tables"])
    except Exception as e:
        print(f"update_preview Error: {e}")

    try:
        with open(app.preview_file, 'w', encoding='utf-8') as f:
            f.write(f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    body {{
                        background-color: {'#1e1e1e' if app.dark_mode else 'white'};
                        color: {'#dcdcdc' if app.dark_mode else 'black'};
                        font-family: sans-serif;
                        padding: 20px;
                        font-size: 32px;
                        line-height: 1.6;
                    }}
                    pre, code {{
                        white-space: pre-wrap;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin-top: 20px;
                        font-size: 32px;
                    }}
                    th, td {{
                        text-align: left;
                        border: 1px solid #ccc;
                        padding: 12px 16px;
                        vertical-align: top;
                        font-size: 32px;
                    }}
                    th {{
                        background-color: #f3f3f3;
                        color: #333;
                    }}
                    tr:nth-child(even) {{
                        background-color: #fafafa;
                    }}
                </style>
                <script>
                window.MathJax = {{
                    tex: {{
                        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
                    }},
                    svg: {{ fontCache: 'global' }}
                }};
                </script>
                <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
            </head>
            <body>{html_content}</body>
            </html>
            """)
        return True
    #    if getattr(app, 'current_file_path', None):
    #        if not hasattr(app, 'browser_opened') or not app.browser_opened:
    #            import webbrowser
    #            webbrowser.open(f"file://{os.path.abspath(app.preview_file)}", new=0)
    #            app.browser_opened = True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate preview: {e}")

#def open_preview_in_browser(preview_file, app):
#    update_preview(app)
#    try:
#        webbrowser.open(f"file://{os.path.abspath(preview_file)}", new=0)
#    except Exception as e:
#        messagebox.showerror("Error", f"Failed to open preview: {e}")

def open_preview_in_browser(preview_file, app):
    if update_preview(app):
        try:
            webbrowser.open(f"file://{os.path.abspath(preview_file)}", new=0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open preview: {e}")
    else:
        messagebox.showinfo("Info", "No document to preview.")
