from setuptools import setup

APP = ['markdown_reader.py']  # 确保这是主文件名
DATA_FILES = ['preview.html']  # 加入你依赖的静态文件
OPTIONS = {
    'iconfile': 'icon.icns',
    'packages': ['markdown2'],  # tkinter 不需要写在这里
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
                'CFBundleTypeIconFile': 'icon.icns',  # 可选：为 md 文件设置图标
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
