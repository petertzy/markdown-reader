
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
