# Windows PDF Export Dependencies

Markdown Reader uses WeasyPrint for PDF export when its native libraries can be loaded. On Windows, install the runtime libraries through MSYS2 UCRT64 and point WeasyPrint at the UCRT64 DLL directory.

## 1. Install MSYS2

Download and install [MSYS2](https://www.msys2.org/). Complete its first-time update steps, then open the **MSYS2 UCRT64** terminal from the Start menu.

## 2. Install Pango

In the MSYS2 UCRT64 terminal, run:

```bash
pacman -S mingw-w64-ucrt-x86_64-pango
```

Accept the package installation prompts. This installs the Pango runtime and its required UCRT64 dependencies.

## 3. Configure WeasyPrint DLL discovery

WeasyPrint uses the `WEASYPRINT_DLL_DIRECTORIES` environment variable to locate the MSYS2 runtime DLLs. The default MSYS2 UCRT64 path is:

```text
C:\msys64\ucrt64\bin
```

For the current PowerShell session, run:

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = 'C:\msys64\ucrt64\bin'
```

To configure it persistently, open **System Properties → Advanced → Environment Variables**, add a user variable named `WEASYPRINT_DLL_DIRECTORIES`, and set its value to the UCRT64 `bin` directory. Open a new terminal after changing the variable.

This is a WeasyPrint DLL-search setting; adding the directory to the general Windows `PATH` is not the documented replacement for this variable.

## 4. Verify the runtime

From the repository root, after installing the Python dependencies, run:

```powershell
uv run python -m weasyprint --info
uv run python -c "from weasyprint import HTML; print('WeasyPrint import OK')"
```

If the import fails, confirm the MSYS2 installation path and the value of `WEASYPRINT_DLL_DIRECTORIES`. If MSYS2 was installed outside `C:\msys64`, use its actual UCRT64 `bin` directory.

## Notes

For upstream installation and native-library troubleshooting details, see the [WeasyPrint first steps documentation](https://doc.courtbouillon.org/weasyprint/latest/first_steps.html).

- PDF export uses WeasyPrint when available. The app can fall back to PyMuPDF, which may produce simpler layouts.
- DOCX export is separate from the WeasyPrint PDF dependency.
- For macOS setup, see [Prepare for macOS](./PrepareForMacUser.md).
- For the PDF export architecture, see [Technical Documentation](./TECHNICAL.md#pdf-export-dependencies).
