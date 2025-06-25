import os
import sys
import tempfile

def get_resource_path(filename):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    elif getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)

import os

def get_preview_file():
    preview_path = os.path.join(tempfile.gettempdir(), "markdown_preview.html")
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write("")
    return preview_path

