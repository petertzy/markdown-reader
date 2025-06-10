from setuptools import setup

APP = ['app.py']
DATA_FILES = ['preview.html']
OPTIONS = {
    'iconfile': 'icon.icns',
    'packages': ['markdown2'],
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
                'CFBundleTypeExtensions': ['md', 'markdown'],
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
