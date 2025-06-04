# Markdown Reader

A clean and intuitive Markdown reader with real-time preview support, dark mode toggle, and drag-and-drop file opening. Compatible with macOS and Windows desktop environments.

## Features

* Real-time preview of Markdown rendered to HTML
* Dark mode toggle
* Drag-and-drop support for `.md` files (requires `tkinterdnd2`)
* Built with pure Python and Tkinter — cross-platform
* Can be bundled as a macOS app using `py2app`
* Opens preview automatically and avoids multiple browser tabs for a smoother experience

---

## Project Overview

<img width="1437" alt="Image" src="https://github.com/user-attachments/assets/9f3bfa17-e9ef-451a-98b8-0ab36953cf03" />

<img width="1436" alt="Image" src="https://github.com/user-attachments/assets/3fe24aea-7018-43b0-873a-5938753db174" />

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
python markdown_reader.py
```

### How to Use

* Open File: Choose `.md` file from the “File → Open File” menu
* Drag-and-Drop: Drag `.md` files directly into the app window
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
* Supports drag-and-drop and live preview updates while avoiding multiple browser tabs

---

## License

This project is licensed under the **MIT License** — free to use, modify, and distribute.

---

## Contributing

All contributions are welcome, including:

* Bug reports
* Feature suggestions
* Pull requests
* Documentation improvements
