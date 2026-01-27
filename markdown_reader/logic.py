import markdown2
import os
import webbrowser
import re
import html2text
from tkinter import messagebox

def update_preview(app):
    if not app.editors:
        return False
    try:
        idx = app.notebook.index(app.notebook.select())
        text_area = app.editors[idx]
        # Use override content if present (from per-selection color logic)
        markdown_text = getattr(app, '_preview_content_override', None)
        if markdown_text is None:
            markdown_text = text_area.get("1.0", "end-1c")
        if hasattr(app, 'file_paths') and app.file_paths:
            try:
                idx = app.notebook.index(app.notebook.select())
                current_path = app.file_paths[idx]
                # Only process images if we have a valid file path
                if current_path is not None:
                    base_dir = os.path.dirname(current_path)
                    markdown_text = fix_image_paths(markdown_text, base_dir)
            except Exception as e:
                # Silently handle cases where file hasn't been saved yet
                pass
        else:
            print("No file_paths attribute or it's empty; skipping fix_image_paths")
        html_content = markdown2.markdown(markdown_text, extras=["fenced-code-blocks", "code-friendly", "tables"])
    except Exception as e:
        print(f"update_preview Error: {e}")

    # Get style from app (with fallback)
    font_family = getattr(app, 'current_font_family', 'Consolas')
    font_size = getattr(app, 'current_font_size', 14)
    fg_color = getattr(app, 'current_fg_color', '#000000')
    bg_color = getattr(app, 'current_bg_color', 'white')
    if getattr(app, 'dark_mode', False):
        bg_color = '#1e1e1e'
        fg_color = '#dcdcdc'

    # For web, use a generic fallback for common fonts
    web_font_family = font_family
    # Add common web-safe fallbacks
    if font_family.lower() in ["arial", "helvetica", "verdana", "tahoma", "trebuchet ms"]:
        web_font_family += ", sans-serif"
    elif font_family.lower() in ["times new roman", "georgia", "garamond", "serif"]:
        web_font_family += ", serif"
    elif font_family.lower() in ["consolas", "courier new", "monospace"]:
        web_font_family += ", monospace"
    else:
        web_font_family += ", sans-serif"

    # Heading sizes relative to base font size
    h1 = font_size + 18
    h2 = font_size + 12
    h3 = font_size + 8
    h4 = font_size + 4
    h5 = font_size + 2
    h6 = font_size + 1
    base = font_size + 2

    try:
        with open(app.preview_file, 'w', encoding='utf-8') as f:
            f.write(f"""
            <html>
            <head>
                <meta charset="UTF-8">
                <style>
                    .copy-button:hover {{
                        background-color: #a5a8b6;
                    }}
                    .copy-button {{
                        position: absolute;
                        top: 10px;
                        right: 10px;
                        background-color: #cacbd0;
                        color: rgb(49, 50, 52);
                        font-size: 0.4em;
                        padding: 1px;
                        border: none;
                        border-radius: 2px;
                        width: auto;
                        min-width: 25px;
                        height: auto;
                        min-height: 15px;
                        cursor: pointer;
                        z-index: 9999;
                    }}
                    body {{
                        background-color: {bg_color};
                        color: {fg_color};
                        font-family: {web_font_family};
                        padding: 20px;
                        font-size: {base}px;
                        line-height: 1.6;
                    }}
                    h1 {{ font-size: {h1}px; }}
                    h2 {{ font-size: {h2}px; }}
                    h3 {{ font-size: {h3}px; }}
                    h4 {{ font-size: {h4}px; }}
                    h5 {{ font-size: {h5}px; }}
                    h6 {{ font-size: {h6}px; }}
                    b, strong {{ font-weight: bold; }}
                    i, em {{ font-style: italic; }}
                    u {{ text-decoration: underline; }}
                    pre code{{
                        background-color: #f4f4f4;
                        color: #000000;
                        font-family: {web_font_family};
                        font-size: {max(font_size - 2, 10)}px;
                        padding: 28px 12px 0px 12px;
                        border-radius: 6px;
                        overflow-x: auto;
                        display: block;
                        max-width: 100%;
                        box-sizing: border-box;
                        white-space: pre;
                    }}
                    code {{
                        background-color: #f4f4f4;
                        color: #000000;
                        font-family: {web_font_family};
                        font-size: {max(font_size - 2, 10)}px;
                        padding: 0 4px;
                        border-radius: 4px;
                        white-space: normal;
                        display: inline;
                    }}
                    img {{
                        max-width: 90vw;
                        max-height: 90vh;
                        height: auto;
                        width: auto;
                        display: block;
                        margin: 10px 0;
                    }}
                    table {{
                        border-collapse: collapse;
                        width: 100%;
                        margin-top: 20px;
                        font-size: {base}px;
                    }}
                    th, td {{
                        text-align: left;
                        border: 1px solid #ccc;
                        padding: 12px 16px;
                        vertical-align: top;
                        font-size: {base}px;
                    }}
                    th {{
                        background-color: #f3f3f3;
                        color: #333;
                    }}
                    tr:nth-child(even) {{
                        background-color: #fafafa;
                    }}
                    @media print {{
                        .copy-button {{
                            display: none !important;
                        }}
                        pre code {{
                            background-color: #f4f4f4 !important;
                            color: #000 !important;
                            display: block !important;
                            white-space: pre-wrap !important;
                            padding: 8px 12px !important;
                            border-radius: 6px !important;
                            overflow-x: visible !important;
                            word-break: break-word !important;
                            word-wrap: break-word !important;
                            -webkit-print-color-adjust: exact;
                            print-color-adjust: exact;
                        }}
                        code {{
                            background-color: #f4f4f4 !important;
                            color: #000 !important;
                            display: inline !important;
                            white-space: normal !important;
                            padding: 0 4px !important;
                            border-radius: 4px !important;
                            -webkit-print-color-adjust: exact;
                            print-color-adjust: exact;
                        }}
                        body {{
                            -webkit-print-color-adjust: exact;
                            print-color-adjust: exact;
                        }}
                    }}
                </style>
                <script>
                    function addCopyButtonToAllCodeBlocks() {{
                        const codeBlocks = document.querySelectorAll('pre code');
                        codeBlocks.forEach(function(codeBlock) {{
                            if (!codeBlock.parentElement.querySelector('.copy-button')) {{
                                const copyButton = document.createElement('button');
                                copyButton.className = 'copy-button';
                                copyButton.textContent = 'Copy';

                                const wrapper = document.createElement('div');
                                wrapper.style.position = 'relative';
                                codeBlock.parentElement.parentNode.insertBefore(wrapper, codeBlock.parentElement);
                                wrapper.appendChild(copyButton);
                                wrapper.appendChild(codeBlock.parentElement);

                                copyButton.addEventListener('click', function() {{
                                    const codeContent = codeBlock.innerText;
                                    const originalText = copyButton.textContent;
                                    copyButton.textContent = 'Copied!';
                                    navigator.clipboard.writeText(codeContent).then(function() {{
                                        setTimeout(function() {{
                                            copyButton.textContent = originalText;
                                        }}, 1000);
                                    }}).catch(function(err) {{
                                        console.error('Could not copy text: ', err);
                                    }});
                                }});

                                copyButton.style.position = 'absolute';
                                copyButton.style.top = '10px';
                                copyButton.style.right = '10px';
                                copyButton.style.border = 'none';
                                copyButton.style.padding = '5px 10px';
                                copyButton.style.cursor = 'pointer';
                                copyButton.style.zIndex = '10';
                            }}
                        }});
                    }}
                    document.addEventListener('DOMContentLoaded', addCopyButtonToAllCodeBlocks);
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
            <body>
                {html_content}
            </body>
            </html>
            """)
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to generate preview: {e}")

def open_preview_in_browser(preview_file, app):
    if update_preview(app):
        try:
            webbrowser.open(f"file://{os.path.abspath(preview_file)}", new=0)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open preview: {e}")
    else:
        messagebox.showinfo("Info", "No document to preview.")

def fix_image_paths(markdown_text, base_path):
    def repl(m):
        alt = m.group(1)
        src = m.group(2)
        if src.startswith(('http://', 'https://', 'file://', '/')):
            return m.group(0)
        abs_path = os.path.abspath(os.path.join(base_path, src))
        abs_url = 'file://' + abs_path.replace('\\', '/')
        return f'![{alt}]({abs_url})'

    return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, markdown_text)


def export_to_html(app, output_path):
    """
    Export the current markdown document to an HTML file.
    
    Args:
        app: The MarkdownReader application instance
        output_path: The path where the HTML file should be saved
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not app.editors:
        messagebox.showinfo("Info", "No document to export.")
        return False
    
    try:
        idx = app.notebook.index(app.notebook.select())
        text_area = app.editors[idx]
        markdown_text = text_area.get("1.0", "end-1c")
        
        # Fix image paths if a file is currently open
        if hasattr(app, 'file_paths') and app.file_paths:
            try:
                current_path = app.file_paths[idx]
                if current_path is not None:
                    base_dir = os.path.dirname(current_path)
                    # Convert file:// paths to relative paths for export
                    def convert_file_url_to_relative(text, base_dir):
                        def repl(m):
                            alt = m.group(1)
                            src = m.group(2)
                            if src.startswith('file://'):
                                # Convert file:// URL back to relative path
                                file_path = src.replace('file://', '')
                                try:
                                    rel_path = os.path.relpath(file_path, base_dir)
                                    return f'![{alt}]({rel_path})'
                                except:
                                    return m.group(0)
                            return m.group(0)
                        return re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', repl, text)
                    
                    markdown_text = convert_file_url_to_relative(markdown_text, base_dir)
            except Exception as e:
                print(f"Warning: Could not process image paths: {e}")
        
        # Convert markdown to HTML
        html_content = markdown2.markdown(
            markdown_text, 
            extras=["fenced-code-blocks", "code-friendly", "tables"]
        )
        
        # Get style from app (with fallback)
        font_family = getattr(app, 'current_font_family', 'Consolas')
        font_size = getattr(app, 'current_font_size', 14)
        fg_color = getattr(app, 'current_fg_color', '#000000')
        bg_color = getattr(app, 'current_bg_color', 'white')
        
        if getattr(app, 'dark_mode', False):
            bg_color = '#1e1e1e'
            fg_color = '#dcdcdc'
        
        # For web, use a generic fallback for common fonts
        web_font_family = font_family
        if font_family.lower() in ["arial", "helvetica", "verdana", "tahoma", "trebuchet ms"]:
            web_font_family += ", sans-serif"
        elif font_family.lower() in ["times new roman", "georgia", "garamond", "serif"]:
            web_font_family += ", serif"
        elif font_family.lower() in ["consolas", "courier new", "monospace"]:
            web_font_family += ", monospace"
        else:
            web_font_family += ", sans-serif"
        
        # Heading sizes relative to base font size
        h1 = font_size + 18
        h2 = font_size + 12
        h3 = font_size + 8
        h4 = font_size + 4
        h5 = font_size + 2
        h6 = font_size + 1
        base = font_size + 2
        
        # Generate complete HTML document
        html_document = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Exported Markdown</title>
    <style>
        body {{
            background-color: {bg_color};
            color: {fg_color};
            font-family: {web_font_family};
            padding: 20px;
            font-size: {base}px;
            line-height: 1.6;
            max-width: 900px;
            margin: 0 auto;
        }}
        h1 {{ font-size: {h1}px; }}
        h2 {{ font-size: {h2}px; }}
        h3 {{ font-size: {h3}px; }}
        h4 {{ font-size: {h4}px; }}
        h5 {{ font-size: {h5}px; }}
        h6 {{ font-size: {h6}px; }}
        b, strong {{ font-weight: bold; }}
        i, em {{ font-style: italic; }}
        u {{ text-decoration: underline; }}
        pre code {{
            background-color: #f4f4f4;
            color: #000000;
            font-family: {web_font_family};
            font-size: {max(font_size - 2, 10)}px;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
            display: block;
            max-width: 100%;
            box-sizing: border-box;
            white-space: pre;
        }}
        code {{
            background-color: #f4f4f4;
            color: #000000;
            font-family: {web_font_family};
            font-size: {max(font_size - 2, 10)}px;
            padding: 2px 4px;
            border-radius: 4px;
            white-space: normal;
            display: inline;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 10px 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-top: 20px;
            font-size: {base}px;
        }}
        th, td {{
            text-align: left;
            border: 1px solid #ccc;
            padding: 12px 16px;
            vertical-align: top;
            font-size: {base}px;
        }}
        th {{
            background-color: #f3f3f3;
            color: #333;
        }}
        tr:nth-child(even) {{
            background-color: #fafafa;
        }}
        blockquote {{
            border-left: 4px solid #ddd;
            padding-left: 15px;
            color: #666;
            margin: 15px 0;
        }}
        a {{
            color: #0066cc;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script>
        window.MathJax = {{
            tex: {{
                inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
                displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
            }},
            svg: {{ fontCache: 'global' }}
        }};
    </script>
</head>
<body>
{html_content}
</body>
</html>"""
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_document)
        
        messagebox.showinfo("Success", f"HTML exported successfully to:\n{output_path}")
        return True
        
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export HTML: {e}")
        return False


def convert_html_to_markdown(html_content):
    """
    Convert HTML content to Markdown format.
    
    Args:
        html_content: HTML string to convert
    
    Returns:
        str: Converted Markdown text
    """
    try:
        # Create html2text converter instance
        h = html2text.HTML2Text()
        
        # Configure converter options for better output
        h.ignore_links = False  # Keep links
        h.ignore_images = False  # Keep images
        h.ignore_emphasis = False  # Keep bold/italic
        h.body_width = 0  # Don't wrap lines
        h.skip_internal_links = False  # Keep internal links
        h.inline_links = True  # Use inline link format [text](url)
        h.protect_links = True  # Protect URLs from being broken
        h.images_to_alt = False  # Don't replace images with alt text
        h.single_line_break = False  # Use proper line breaks
        h.mark_code = True  # Mark code blocks
        
        # Convert HTML to Markdown
        markdown_text = h.handle(html_content)
        
        # Clean up excessive blank lines
        markdown_text = re.sub(r'\n{3,}', '\n\n', markdown_text)
        
        return markdown_text.strip()
        
    except Exception as e:
        messagebox.showerror("Conversion Error", f"Failed to convert HTML to Markdown: {e}")
        return html_content  # Return original HTML if conversion fails