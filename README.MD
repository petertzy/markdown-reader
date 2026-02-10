# Markdown Reader

A clean and intuitive Markdown reader with real-time preview support, dark mode toggle, and drag-and-drop file opening. Compatible with macOS and Windows desktop environments.

## Features

* Real-time preview of Markdown rendered to HTML
* Dark mode toggle
* Drag-and-drop support for `.md`, `.html`, and `.pdf` files with automatic conversion to Markdown (requires `tkinterdnd2`)
* Built with pure Python and Tkinter — cross-platform
* Can be bundled as a macOS app using `py2app`
* Opens preview automatically and avoids multiple browser tabs for a smoother experience

---

## Editor Overview

<img width="1436" alt="Image" src="https://github.com/user-attachments/assets/0e5400c8-e26b-4309-9fa7-2127890d0f8c" />

---

## Preview Overview

<img width="1417" alt="Image" src="https://github.com/user-attachments/assets/a0e1ef35-0216-4d48-8dca-2dfde8244bad" />

---

## Installation & Usage

### 1. Clone the repository

```bash
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# .\venv\Scripts\activate  # Windows (cmd/powershell)
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

💡 If drag-and-drop doesn't work on macOS, consider using the [tkinterDnD2 fork](https://github.com/pmgagne/tkinterDnD2).

---

## Running the Application

```bash
python app.py
```

### How to Use

* Open File: Choose `.md`, `.html`, or `.pdf` file from the "File → Open File" menu
* Drag-and-Drop: Drag `.md`, `.html`, or `.pdf` files directly into the app window (HTML and PDF files are automatically converted to Markdown)
* Dark Mode: Toggle via “View → Toggle Dark Mode”
* Preview: Automatically opens in your web browser, only one tab is opened per session

---

## Packaging as a macOS App (Optional)

To bundle this app as a `.app`, install `py2app` and create a `setup.py` script:

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

* GUI: `tkinter`, `tkinterdnd2`
* Markdown Engine: `markdown2`
* HTML Preview: Dynamically generated HTML opened in the default browser
* File Conversion: `html2text` for HTML, `pypdf` for PDF
* Supports drag-and-drop and live preview updates while avoiding multiple browser tabs

---

## License

This project is licensed under a **custom license**:

- All contributors have full rights to use, modify, distribute, and use this project for commercial or non-commercial purposes.
- All other users may use and modify the code for **non-commercial purposes only**.
- **Commercial use by non-contributors is strictly prohibited** without explicit written permission from the project creator.

Please contact the project owner to request commercial licensing.


---

## Contributing

All contributions are welcome, including:

* Bug reports
* Feature suggestions
* Pull requests
* Documentation improvements
