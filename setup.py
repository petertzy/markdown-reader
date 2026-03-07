import sys
from setuptools import setup

# Increase recursion limit to handle deep dependency trees
sys.setrecursionlimit(5000)

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'packages': ['markdown_reader', 'pygments', 'tkinterdnd2', 'PIL'],
    'includes': ['tkinter', 'markdown2', 'docx', 'html2text', 'watchdog', 'tkinterdnd2', 'pygments.lexers', 'pygments.lexers.shell', 'PIL', 'PIL.Image'],
    'excludes': ['numpy', 'scipy', 'matplotlib', 'docling', 'pymupdf', 'datasets', 'torch', 'tensorflow', 'sympy', 'pandas', 'PyQt6', 'PyQt5', 'PySide6', 'PySide2', 'jupyter', 'ipython', 'IPython', 'sip', 'PyQt6.sip', 'PyQt5.sip'],
    'semi_standalone': False,
    'site_packages': False,
    'plist': {
        'CFBundleName': 'MarkdownReader',
        'CFBundleDisplayName': 'MarkdownReader',
        'CFBundleIdentifier': 'com.example.markdownreader',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.14.0',
            'NSHighResolutionCapable': True,
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'Markdown File',
                # include both lowercase and uppercase extensions to ensure macOS
                # recognizes files regardless of extension case
                'CFBundleTypeExtensions': ['md', 'MD', 'markdown', 'MARKDOWN'],
                'CFBundleTypeMIMETypes': ['text/markdown'],
                'CFBundleTypeRole': 'Editor',
                'LSHandlerRank': 'Owner',
                'CFBundleTypeIconFile': 'icon.icns',
            }
        ],
    }
}

setup(
    app=APP,
    name='MarkdownReader',
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
