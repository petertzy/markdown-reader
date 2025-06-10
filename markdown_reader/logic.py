import markdown2
import os
import webbrowser
from tkinter import messagebox

def update_preview(app):
    markdown_text = app.text_area.get('1.0', 'end')
    html_content = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "code-friendly", "tables"])

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
            <body>{html_content}</body>
            </html>
            """)
        if not hasattr(app, 'browser_opened') or not app.browser_opened:
            webbrowser.open(f"file://{os.path.abspath(app.preview_file)}", new=0)
            app.browser_opened = True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate preview: {e}")

def open_preview_in_browser(preview_file):
    try:
        webbrowser.open(f"file://{os.path.abspath(preview_file)}", new=0)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to open preview: {e}")
