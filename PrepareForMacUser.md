
For Mac users, you should first run the following additional command:
```bash
brew install cairo pango gdk-pixbuf libffi
```
Then reactivate your virtual environment:
```bash
deactivate
source venv/bin/activate
```
#### If you are using Apple Silicon (M1/M2/M3/M4)

Run:
```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```
Then test:
```bash
python -c "from weasyprint import HTML; print('OK')"
```
#### If you are using an Intel Mac

Run:
```bash
export DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib
```
#### Make It Permanent (Recommended)

If the previous step works, add the environment variable to your shell configuration.
If you are using **zsh**, open:
```bash
nano ~/.zshrc
```
Add the following line:

#### Apple Silicon
```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```
#### Intel Mac
```bash
export DYLD_FALLBACK_LIBRARY_PATH=/usr/local/lib
```
Save the file, then run:
```bash
source ~/.zshrc
```

---

## Drag-and-Drop Functionality

### Apple Silicon (M1/M2/M3/M4) Known Issues

⚠️ **Important**: tkinterdnd2 library currently **does not work** on Apple Silicon Macs due to architecture compatibility issues.

**Root Cause**:
- tkinterdnd2 dynamic link library (.dylib) files are only compiled for Intel (x86_64) architecture
- Apple Silicon requires ARM64 architecture library files
- All known forks and versions have the same issue

**Expected Error Messages**:
```
Warning: tkinterdnd2 not installed, drag-and-drop will be disabled
Error: Unable to load tkdnd library
⚠️ Drag-and-drop binding failed: '_tkinter.tkapp' object has no attribute 'drop_target_register'
```

**This does NOT affect the main functionality!** All other features still work normally.

### Alternative Solutions

Although drag-and-drop is unavailable, you can open files through:

1. **Use Menu**: File → Open File (recommended)
2. **Command Line**: `python app.py your_file.md`
3. **Finder Integration**: Right-click .md file → Open With

### Intel Mac Users

If you are using an Intel Mac and drag-and-drop doesn't work, try:

```bash
pip uninstall tkinterdnd2
pip install git+https://github.com/pmgagne/tkinterDnD2.git
```

### Future Solutions

Wait for tkinterdnd2 to release an ARM64-compatible version. You can follow these projects:
- https://github.com/pmgagne/tkinterDnD2
- https://github.com/Eliav2/tkinterdnd2
