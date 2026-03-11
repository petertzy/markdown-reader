import os
import signal
import sys
import tkinter as tk

import ttkbootstrap as ttkb
from ttkbootstrap.constants import *

from markdown_reader.ui import MarkdownReader


def _icon_debug_enabled():
    return os.environ.get("MARKDOWN_READER_DEBUG_ICON", "").strip() == "1"


def _icon_log(message):
    if _icon_debug_enabled():
        print(f"[icon] {message}")


def _resolve_icon_path():
    """Resolve icon path for both source runs and py2app bundles."""

    if getattr(sys, "frozen", False):
        resource_path = os.environ.get("RESOURCEPATH")
        if resource_path:
            return os.path.join(resource_path, "icon.icns")
        return os.path.join(os.path.dirname(sys.executable), "icon.icns")

    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.icns")


def _set_macos_app_icon_once(root):
    """Apply the macOS app icon one time."""

    if sys.platform != "darwin":
        return

    icon_path = _resolve_icon_path()
    _icon_log(f"resolved path: {icon_path}")
    if not os.path.exists(icon_path):
        _icon_log("icon file not found")
        return

    # In bundled mode, prefer native AppKit only to avoid Dock icon flicker.
    is_frozen = getattr(sys, "frozen", False)
    if not is_frozen:
        # Tk-level icon hints for development runs.
        try:
            root.tk.call("::tk::mac::iconBitmap", icon_path)
            _icon_log("tk mac iconBitmap: ok")
        except tk.TclError:
            _icon_log("tk mac iconBitmap: failed")
            pass

        try:
            root.iconbitmap(icon_path)
            _icon_log("root.iconbitmap: ok")
        except tk.TclError:
            _icon_log("root.iconbitmap: failed")
            pass

    # Cocoa-level icon set to avoid runtime icon replacement.
    try:
        from AppKit import NSApplication, NSImage  # type: ignore[import-not-found]

        image = NSImage.alloc().initWithContentsOfFile_(icon_path)
        if image is not None:
            NSApplication.sharedApplication().setApplicationIconImage_(image)
            _icon_log("AppKit setApplicationIconImage: ok")
            return
        _icon_log("AppKit image load returned None")
    except Exception:
        _icon_log("AppKit path failed, trying ctypes fallback")
        # Fallback: call Objective-C runtime directly when pyobjc/AppKit is unavailable.
        try:
            import ctypes
            import ctypes.util

            objc_path = ctypes.util.find_library("objc")
            appkit_path = ctypes.util.find_library("AppKit")
            if not objc_path or not appkit_path:
                return

            objc = ctypes.cdll.LoadLibrary(objc_path)
            ctypes.cdll.LoadLibrary(appkit_path)

            objc.objc_getClass.restype = ctypes.c_void_p
            objc.objc_getClass.argtypes = [ctypes.c_char_p]
            objc.sel_registerName.restype = ctypes.c_void_p
            objc.sel_registerName.argtypes = [ctypes.c_char_p]

            msg_send = objc.objc_msgSend

            def send(obj, selector, *args, restype=ctypes.c_void_p, argtypes=None):
                msg_send.restype = restype
                msg_send.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + (
                    argtypes or []
                )
                sel = objc.sel_registerName(selector.encode("utf-8"))
                return msg_send(obj, sel, *args)

            ns_string_cls = objc.objc_getClass(b"NSString")
            ns_image_cls = objc.objc_getClass(b"NSImage")
            ns_app_cls = objc.objc_getClass(b"NSApplication")
            if not ns_string_cls or not ns_image_cls or not ns_app_cls:
                return

            ns_string = send(ns_string_cls, "alloc")
            ns_string = send(
                ns_string,
                "initWithUTF8String:",
                icon_path.encode("utf-8"),
                argtypes=[ctypes.c_char_p],
            )

            ns_image = send(ns_image_cls, "alloc")
            ns_image = send(
                ns_image,
                "initWithContentsOfFile:",
                ns_string,
                argtypes=[ctypes.c_void_p],
            )
            if not ns_image:
                return

            ns_app = send(ns_app_cls, "sharedApplication")
            send(
                ns_app,
                "setApplicationIconImage:",
                ns_image,
                restype=None,
                argtypes=[ctypes.c_void_p],
            )
            _icon_log("ctypes setApplicationIconImage: ok")
        except Exception:
            _icon_log("ctypes fallback failed")
            pass


def _set_macos_app_icon(root, attempts=20, delay_ms=250):
    """Repeatedly enforce macOS icon for a short startup window."""

    if sys.platform != "darwin":
        return

    _set_macos_app_icon_once(root)

    # In bundled app mode, repeated icon writes can cause visible flicker.
    # Keep reinforcement for `python app.py` only.
    if getattr(sys, "frozen", False):
        return

    if attempts <= 1:
        return
    root.after(delay_ms, lambda: _set_macos_app_icon(root, attempts - 1, delay_ms))


def handle_open_file(event):
    """
    Handles file open events from macOS.

    :param event event: The open file event from macOS.
    """

    file_path = event
    if os.path.isfile(file_path) and file_path.lower().endswith(
        (".md", ".markdown", ".html", ".htm", ".pdf")
    ):
        app.load_file(file_path)


def _install_sigint_handler(root, app):
    """Route Ctrl-C through the same shutdown path as a normal window close."""

    previous_handler = signal.getsignal(signal.SIGINT)

    def _handle_sigint(signum, frame):
        try:
            root.after(0, app.quit)
        except Exception:
            app.quit()

    signal.signal(signal.SIGINT, _handle_sigint)
    return previous_handler


if __name__ == "__main__":
    # Use ttkbootstrap window directly for stable styling across Python/Tk versions.
    root = ttkb.Window(themename="darkly")
    _set_macos_app_icon(root)

    # Ensure window is resizable
    root.resizable(width=True, height=True)

    app = MarkdownReader(root)

    # Handle file open events from macOS Finder
    root.createcommand(
        "::tk::mac::OpenDocument", lambda *args: handle_open_file(args[0])
    )

    # Handle file opening from command line
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            # Skip macOS system parameters (process serial number)
            if arg.startswith("-psn"):
                continue
            # Convert to absolute path
            file_path = os.path.abspath(arg)
            if os.path.isfile(file_path) and file_path.lower().endswith(
                (".md", ".markdown", ".html", ".htm", ".pdf")
            ):
                app.load_file(file_path)
                break  # Only open the first file

    previous_sigint_handler = _install_sigint_handler(root, app)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        app.quit()
    finally:
        try:
            app.quit()
        except Exception:
            pass

        try:
            signal.signal(signal.SIGINT, previous_sigint_handler)
        except Exception:
            pass
