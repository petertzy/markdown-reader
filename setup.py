import sys

# modulegraph (used internally by py2app) scans every imported package's AST.
# Python 3.14's richer AST node structure causes it to recurse much deeper than
# older versions, exceeding the default limit of 1000 and crashing the build.
# 5000 is enough for fontTools, weasyprint and other deep packages.
sys.setrecursionlimit(5000)

from py2app.build_app import py2app as py2app_build
from setuptools import setup


class py2app_cmd(py2app_build):
    """Subclass that clears install_requires before py2app processes it.

    py2app >= 0.28 no longer supports install_requires (all dependencies must
    already be present in the active venv).  setuptools auto-populates
    install_requires from pyproject.toml's [project].dependencies, so we
    clear it here to avoid the "install_requires is no longer supported" error.
    """

    def finalize_options(self):
        self.distribution.install_requires = []
        super().finalize_options()


APP = ["app.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "iconfile": "icon.icns",
    "packages": [
        "markdown_reader",
        "pygments",
        "ttkbootstrap",
        "PIL",
        "keyring",
        # WeasyPrint and its direct pure-Python dependencies.
        # requests/certifi/charset_normalizer/idna/urllib3 are auto-discovered
        # from the source; only list packages modulegraph tends to miss.
        "weasyprint",
        "pydyf",
        "cssselect2",
        "tinycss2",
        "pyphen",
        "fontTools",
    ],
    "includes": [
        "tkinter",
        "markdown2",
        "docx",
        "html2text",
        "watchdog",
        "pygments.lexers",
        "pygments.lexers.shell",
        "PIL",
        "PIL.Image",
        "PIL.ImageTk",
        "keyring.backends",
        "keyring.backends.macOS",
        # WeasyPrint sub-modules that use dynamic/late imports
        "weasyprint.css",
        "weasyprint.document",
        "weasyprint.formatting_structure",
        "weasyprint.layout",
        "weasyprint.pdf",
        "weasyprint.svg",
        "weasyprint.text",
        "weasyprint.text.ffi",
        "weasyprint.text.fonts",
        "fontTools.ttLib",
        "fontTools.subset",
    ],
    # Exclude heavy optional deps that are not needed at runtime.
    "excludes": [
        "numpy",
        "scipy",
        "matplotlib",
        "docling",
        "html5lib",  # not installed; excluding prevents modulegraph chasing it
    ],
    "plist": {
        "CFBundleName": "MarkdownReader",
        "CFBundleDisplayName": "MarkdownReader",
        "CFBundleIdentifier": "com.petertzy.markdownreader",
        "CFBundleIconFile": "icon.icns",
        "CFBundleVersion": "1.0.0",
        "CFBundleShortVersionString": "1.0.0",
        "LSMinimumSystemVersion": "10.14.0",
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Markdown File",
                # include both lowercase and uppercase extensions to ensure macOS
                # recognizes files regardless of extension case
                "CFBundleTypeExtensions": ["md", "MD", "markdown", "MARKDOWN"],
                "CFBundleTypeMIMETypes": ["text/markdown"],
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
                "CFBundleTypeIconFile": "icon.icns",
            }
        ],
    },
}

setup(
    app=APP,
    name="MarkdownReader",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    cmdclass={"py2app": py2app_cmd},
)
