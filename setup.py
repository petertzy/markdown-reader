from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': 'icon.icns',
    'packages': ['markdown_reader', 'pygments'],
    'includes': ['tkinter', 'markdown2', 'docx', 'html2text', 'watchdog', 'pygments.lexers', 'pygments.lexers.shell'],
    'excludes': ['PIL', 'numpy', 'scipy', 'matplotlib'],
    'plist': {
        'CFBundleName': 'MarkdownReader',
        'CFBundleDisplayName': 'MarkdownReader',
        'CFBundleIdentifier': 'com.example.markdownreader',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSMinimumSystemVersion': '10.14.0',
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
