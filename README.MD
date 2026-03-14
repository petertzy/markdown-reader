# Markdown Reader

Markdown Reader is a clean and intuitive Markdown editor/reader with real-time preview support and dark mode toggle. It is compatible with macOS and Windows desktop environments and built with pure Python and Tkinter.

---

## Features

* Tabbed Markdown editing with real-time HTML preview.
* **AI-Powered Translation**: Translate Markdown documents while preserving formatting (supports OpenRouter, OpenAI, and Anthropic).
* **API Key Management**: Missing or rejected provider keys trigger an in-app dialog, and keys can be saved to the app's per-user settings file.
* **Progressive Translation Rendering**: Long translations are split into smaller chunks, inserted into the editor as they complete, auto-scrolled into view, and tracked with a progress bar.
* Dark mode toggle.
* **Advanced Table Editor**: Interactive table insertion with customizable rows and columns.
* **Dual PDF Conversion**: Fast PyMuPDF mode or advanced [Docling](https://github.com/docling-project/docling) mode for complex documents.
* Built with pure Python, Tkinter, and ttkbootstrap — cross-platform.
* Can be bundled as a macOS app using `py2app`.
* Opens preview automatically and avoids multiple browser tabs for a smoother experience.
* Multi-provider AI failover: Automatically switches to fallback providers on rate-limit/auth/server errors.

---

## Editor Overview

<img width="1428" height="737" alt="Image" src="https://github.com/user-attachments/assets/4f584f5b-dd1a-4d74-9a99-ca2cd90a9994" />

---

## Preview Overview

<img width="1417" height="474" alt="Image" src="https://github.com/user-attachments/assets/9a0006ed-d269-428b-a41f-e512cc7ba9c9" />

---

## Installation & Usage

#### 1. Clone the repository

```bash
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader
```

#### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# .\venv\Scripts\activate  # Windows (cmd/powershell)
```

#### 3. Install dependencies

For Mac users, you should first complete the preparation steps described in the [PrepareForMacUser](./doc/PrepareForMacUser.md) file.

For Windows users, WeasyPrint requires additional system libraries. Complete the preparation steps described in the [PrepareForWindowsUser](./doc/PrepareForWindowsUser.md) file before running `pip install`.

```bash
pip install -r requirements.txt
```

---

## Running the Application

```bash
python app.py
```

### How to Use

* **Open File**: Choose `.md`, `.markdown`, `.html`, `.htm`, or `.pdf` from the "File → Open File" menu.
* **Dark Mode**: Toggle via "View → Toggle Dark Mode".
* **Preview**: Automatically opens in your web browser, only one tab is opened per session.
* **AI Translation**: 
  - Translate selected text: "Edit → Translate with AI → Translate Selected Text with AI"
  - Translate full document: "Edit → Translate with AI → Translate Full Document with AI"
  - Select source and target languages from dropdown menus
  - Configure provider/model/API keys: "Settings → AI Provider & API Keys..."
  - If a key is missing or rejected, the app prompts for the correct provider key and can save it in the app settings file
  - Large translations appear progressively in the editor with automatic scrolling and a visible progress bar
* **Table Insertion**: Use "Table → Insert Table" to create custom tables with interactive cell editing.
* **PDF Conversion Modes**: 
  - Fast mode (default): Uses PyMuPDF for quick extraction
  - Advanced mode: Enable "Tools → Use Advanced PDF Conversion (Docling)" for complex documents
  - View mode info: "Tools → PDF Converter Info"

---

## Packaging as a macOS App (Optional)

To bundle this app as a `.app`, use the included `setup.py` script:

### Build the App

```bash
rm -rf build dist
python setup.py py2app
```

The generated app will be located in the `dist/` folder. You can launch it by double-clicking. To use it like a regular app, move it to your Applications folder.

---

## Exit the Virtual Environment
```bash
deactivate
```

## Submit Changes to Git
```bash
git add .
git commit -m "Update"  # Replace "Update" with a meaningful commit message
git push
```

## Technical Details

* GUI: `tkinter`, `ttkbootstrap`
* Markdown Engine: `markdown2`
* HTML Preview: Dynamically generated HTML opened in the default browser
* File Conversion: `html2text` for HTML, `PyMuPDF` and `docling` for PDF import (`pypdf` is used as a fallback when PyMuPDF is unavailable)
* PDF Export: `weasyprint`
* AI Translation: `requests` for API communication with OpenRouter, OpenAI, and Anthropic
* Configuration: Per-user settings JSON for provider, model, and API keys. Paths: macOS `~/Library/Application Support/MarkdownReader/settings.json`; Windows `%APPDATA%/MarkdownReader/settings.json`; Linux `~/.config/markdown-reader/settings.json`
* Auto-failover: Automatically switches AI providers when the primary provider returns rate-limit/auth/server errors

---

## System Requirements:
Python >= 3.10

---

## AI-powered translation:
To enable AI-powered translation features, you need to set up API keys:

1. Open `Settings -> AI Provider & API Keys...`.
2. Choose provider and model.
3. Enter API key and save.

The app stores provider, model, and API key in a per-user JSON file:

- macOS: `~/Library/Application Support/MarkdownReader/settings.json`
- Windows: `%APPDATA%/MarkdownReader/settings.json`
- Linux: `~/.config/markdown-reader/settings.json`

**How to get API keys:**
- **OpenRouter** (recommended for free tier): [openrouter.ai](https://openrouter.ai/)
- **OpenAI**: [platform.openai.com](https://platform.openai.com/)
- **Anthropic**: [console.anthropic.com](https://console.anthropic.com/)

API keys are saved in the same per-user settings JSON file.

On macOS and Linux, the app writes settings with owner-only file permissions when possible.

The app will automatically switch to a fallback provider when the primary provider returns rate-limit/auth/server errors.

---

## License

This project is licensed under the **MIT License**.  
See the [LICENSE](LICENSE.md) file for the full text.

---

## Contributing

All contributions are welcome, including:

- Bug reports
- Feature suggestions
- Pull requests
- Documentation improvements

Please see our [CONTRIBUTING](CONTRIBUTING.md) guide for more details on how to get started, submit changes, or report issues.

