<div align="center">
  <h1>Markdown Reader</h1>
  <p><b>The open-source, local-first Markdown editor with native AI capabilities.</b></p>
  
  [![macOS Apple Silicon](https://img.shields.io/badge/macOS-Apple_Silicon-black?logo=apple)](#desktop-downloads)
  [![Windows x64](https://img.shields.io/badge/Windows-x64-blue?logo=windows)](#desktop-downloads)
  [![Linux x64](https://img.shields.io/badge/Linux-x64-yellow?logo=linux)](#desktop-downloads)
  
  <br />
  <img src="https://github.com/user-attachments/assets/ac3351a8-dd2a-445b-9f1f-4754faeef509" alt="Markdown Reader desktop preview" width="800">
</div>

---

## 🌟 Why Markdown Reader?

Most modern writing apps force you to choose between **privacy** and **power**. Cloud-based AI editors train on your data, while local editors often lack intelligent features.

**Markdown Reader bridges the gap.** It is a native desktop application built on Tauri, ensuring your files stay locally on your machine. But it also seamlessly integrates with **OpenAI, Anthropic, OpenRouter, and Local LLMs**, bringing powerful AI-assisted writing directly to your offline workflow.

### Key Features
* 🔒 **Local-First Architecture**: Your files never leave your machine unless you explicitly call an external AI API.
* 🤖 **Bring-Your-Own-AI**: Configure OpenAI, Anthropic, or OpenRouter with your own API keys.
* ✍️ **Intelligent Editing**: AI-assisted translation, summarization, formatting, and code-block cleanup.
* 🛡️ **Audit & Rollback**: Review all AI suggestions before applying them. Reject or rollback changes with a single click.
* 🖥️ **Native Desktop Feel**: Built with Next.js and packaged with Tauri for blazing-fast performance.

---

## 🚀 Quick Start

Get the app running locally for development in under a minute:

```bash
# Prerequisites: Python 3.11+, Node.js 18+, and uv
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader

# Install dependencies
uv sync
cd frontend && npm install && cd ..

# Configure frontend environment variables
cp frontend/.env.local.example frontend/.env.local

# Launch the Tauri desktop app
./scripts/dev-tauri.sh
```

> **Note for Contributors:** After cloning, run `uv sync --extra dev` and `uv run pre-commit install` to set up linting hooks.

---

## 📦 Desktop Downloads

We provide official desktop release builds through GitHub Actions.

| OS | Architecture | Download |
|---|---|---|
| **macOS** | Apple Silicon | [Download .dmg](https://petertzy.github.io/markdown-reader/) |
| **Windows** | x64 | [Download .exe](https://petertzy.github.io/markdown-reader/) |
| **Linux** | x64 | [Download .AppImage](https://petertzy.github.io/markdown-reader/) |

*(Note: macOS Intel builds are currently unsupported due to advanced PDF dependency constraints).*

---

## 🏗️ Architecture

Markdown Reader is split into three main layers to ensure maximum performance and maintainability:

1. **Backend (`/backend`)**: A blazing-fast FastAPI application handling rendering, export, and all AI API communications.
2. **Frontend (`/frontend`)**: A Next.js UI providing the rich editor experience, packaged within a Tauri desktop shell.
3. **Legacy (`/markdown_reader`)**: Legacy Tkinter app logic preserved for historical reference.

When packaged for desktop use, the Python backend is bundled as a silent Tauri sidecar process, dynamically assigning ports at runtime to avoid conflicts.

---

## 🤝 Contributing

Contributions are highly welcome! Whether you're fixing a bug, suggesting a feature, or helping us write documentation, we'd love to have you.

To get started:
1. `git checkout -b your-feature-branch`
2. Run linting: `uv run ruff check .`
3. Run tests: `uv run python -m unittest discover -s tests`
4. Open a Pull Request!

See our full [Contribution Guidelines](CONTRIBUTING.md) for more details.

---

<div align="center">
  Released under the MIT License. See <a href="LICENSE.md">LICENSE.md</a> for details.
</div>
