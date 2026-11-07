# macOS PDF Export Dependencies

Markdown Reader uses WeasyPrint for PDF export when the required native libraries can be loaded. The development helper adds `/opt/homebrew/lib` to `DYLD_FALLBACK_LIBRARY_PATH` automatically when that directory exists. A manual setup is useful when running Python or the backend outside the helper.

## 1. Install Homebrew libraries

Install Homebrew if it is not already available, then run:

```bash
brew install glib pango cairo gdk-pixbuf libffi
```

## 2. Make Homebrew libraries discoverable

For Apple Silicon Macs using the standard Homebrew location:

```bash
export DYLD_FALLBACK_LIBRARY_PATH="/opt/homebrew/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
```

For Intel Macs using the standard Homebrew location:

```bash
export DYLD_FALLBACK_LIBRARY_PATH="/usr/local/lib${DYLD_FALLBACK_LIBRARY_PATH:+:$DYLD_FALLBACK_LIBRARY_PATH}"
```

If Homebrew is installed somewhere else, use the corresponding library directory. To make the setting persistent in zsh, add the appropriate export line to `~/.zshrc` and run `source ~/.zshrc`.

## 3. Verify WeasyPrint

After synchronizing the project Python environment with `uv sync`, run:

```bash
uv run python -c "from weasyprint import HTML; print('WeasyPrint import OK')"
```

If the import succeeds but PDF export still falls back, inspect the reported WeasyPrint/system-library diagnostics and confirm that the shell launching the backend has the library path.

## Notes

For upstream installation and native-library troubleshooting details, see the [WeasyPrint first steps documentation](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html).

- The project development helper adds the Apple Silicon Homebrew library path when `/opt/homebrew/lib` exists; it does not automatically add the Intel `/usr/local/lib` path.
- WeasyPrint is preferred when available. The application can fall back to PyMuPDF for PDF export, with simpler layout fidelity.
- For Windows, follow [Prepare for Windows](./PrepareForWindowsUser.md).
- For architecture and export details, see [Technical Documentation](./TECHNICAL.md#pdf-export-dependencies).
