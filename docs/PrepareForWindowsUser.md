For Windows users, WeasyPrint requires native system libraries (Cairo, Pango) that are not available by default. The recommended way to install them is via **MSYS2**.

#### 1. Install MSYS2

Download and install MSYS2 from [https://www.msys2.org/](https://www.msys2.org/), then follow the first-time setup instructions on the site.

#### 2. Install the required libraries

Open the **MSYS2 UCRT64** terminal (search for "MSYS2 UCRT64" in the Start menu) and run:

```bash
pacman -S mingw-w64-ucrt-x86_64-pango
```

#### 3. Add MSYS2 to your Windows PATH

Add the MSYS2 UCRT64 `bin` directory to your Windows `PATH` environment variable:

```
C:\msys64\ucrt64\bin
```

To do this permanently:
1. Open **System Properties** → **Advanced** → **Environment Variables**
2. Under **System variables**, select `Path` and click **Edit**
3. Click **New** and add `C:\msys64\ucrt64\bin`
4. Click **OK** to save

#### 4. Reactivate your virtual environment

Open a new Command Prompt or PowerShell window (so the updated PATH takes effect), then reactivate your virtual environment:

```cmd
.\.venv\Scripts\activate
```

#### 5. Verify the installation

```cmd
python -c "from weasyprint import HTML; print('OK')"
```

If you see `OK`, WeasyPrint is working correctly and you can proceed with installing the remaining dependencies.

> **Note:** If MSYS2 was installed to a different directory (not `C:\msys64`), adjust the path in step 3 accordingly.
