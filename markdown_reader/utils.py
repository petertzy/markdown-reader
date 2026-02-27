import os
import sys
import tempfile


def get_resource_path(filename): # Potentially unused function?
    """
    Gets the filepath of a resource depending on the system's attributes.

    :param string filename: The file name for the resource to be returned.

    :return: A string with the filename joined onto its relevant file path.
    """
    
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    elif getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), filename)
    else:
        return os.path.join(os.path.abspath("."), filename)


def get_preview_file():
    """
    Returns the file path for the Markdown preview file based on the file's directory.

    :return: A string containing the file path for the temporary HTML preview file.
    """
    
    preview_path = os.path.join(tempfile.gettempdir(), "markdown_preview.html")
    with open(preview_path, 'w', encoding='utf-8') as f:
        f.write("")
    return preview_path
