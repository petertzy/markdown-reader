# Markdown Reader

Markdown Reader is a desktop Markdown editor and reader built with a Next.js
frontend, a local FastAPI backend, AI-assisted editing tools, and native
desktop packaging through Tauri.

![Markdown Reader desktop preview](https://github.com/user-attachments/assets/ac3351a8-dd2a-445b-9f1f-4754faeef509)

---

## Quick Start

Get the app running in under a minute:

```bash
# Prerequisites: Python 3.11+, Node.js 18+, and uv
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader

# Install dependencies
uv sync
cd frontend && npm install && cd ..

# Configure frontend
cp frontend/.env.local.example frontend/.env.local

# Launch in development mode (opens a Tauri desktop window)
./scripts/dev-tauri.sh
```

Open `http://127.0.0.1:8000/docs` for the backend API docs. Press `Ctrl+C` to stop.

> **For contributors:** After cloning, also run `uv sync --extra dev` and `uv run pre-commit install` to set up linting hooks.

---

## Features

- Edit Markdown with a split editor and live preview experience.
- Open and work with Markdown files from a native desktop app window.
- Import content from Markdown, HTML, and PDF.
- Use AI-assisted translation, summarization, table-of-contents generation,
  formatting, and code-block cleanup.
- Configure OpenAI Compatible, OpenRouter, OpenAI, and Anthropic providers from
  the app.
- Review AI suggestions before applying them, with support for rejection,
  rollback, and audit tracking.
- Export rendered documents through the local backend.
- Build a single packaged desktop app with the Python backend bundled as a
  Tauri sidecar.

---

## Desktop Downloads

Official desktop release builds are published through GitHub Actions for:

- macOS Apple Silicon (`aarch64-apple-darwin`)
- Windows x64 (`x86_64-pc-windows-msvc`)
- Linux x64 (`x86_64-unknown-linux-gnu`)

macOS Intel builds are not part of the current release matrix. Recent macOS
devices use Apple Silicon, and the app's advanced PDF dependency chain no
longer provides all required wheels for macOS Intel.

The public download page is served from `distribution/` through GitHub Pages:
<https://petertzy.github.io/markdown-reader/>.

---

## Architecture

Markdown Reader is split into three main layers:

```text
MarkdownReader/
├── backend/              # FastAPI app, routers, rendering, export, and AI APIs
├── frontend/             # Next.js UI and Tauri desktop shell
├── markdown_reader/      # Legacy Tkinter app logic (preserved for reference)
├── scripts/              # Development and release helper scripts
├── tests/                # Python tests for backend and AI workflow logic
├── docs/                 # Additional project and platform notes
├── README_REFACTORING.md # Archived refactoring/migration notes
└── README_OLD.MD         # Legacy Tkinter-era documentation
```

### Development mode

- Launches a real Tauri desktop window instead of a browser tab.
- Frontend runs from the Next.js dev server on `http://localhost:3000`.
- Backend runs from the FastAPI dev server on `http://127.0.0.1:8000`.
- Recommended start command: `./scripts/dev-tauri.sh`.

### Desktop (packaged) mode

- Users launch one app only: `Markdown Reader.app`.
- Python backend is bundled as a Tauri sidecar process.
- Backend port is dynamically assigned by the OS at runtime (no hard-coded
  ports in desktop mode).

---

## Usage

After the desktop window opens, use Markdown Reader to:

- Open Markdown files for editing and live preview.
- Work with multiple document tabs.
- Import supported document formats (Markdown, HTML, PDF).
- Use AI tools from the AI panel to translate, summarize, format, or prepare
  document edits. Review suggested changes before applying them.
- Configure AI providers, models, base URLs, and API keys from the app settings
  (keys are saved via the system credential store).

---

## Backend API

The FastAPI backend exposes these route groups:

- `/api/files/*`
- `/api/markdown/*`
- `/api/ai/*`
- `/api/export/*`

Health endpoint: `GET /api/health`

Interactive docs (dev mode):
- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Running Services Separately

Most contributors should use `./scripts/dev-tauri.sh`, but you can start
services individually for debugging:

```bash
# Backend
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend (in a separate terminal)
cd frontend && npm run dev

# Tauri shell (with frontend dev server already running)
cd frontend && npm run tauri:dev
```

---

## Building the Desktop App

Release bundles are built by `.github/workflows/release.yml` when a `v*` tag is
pushed or the workflow is run manually. The workflow uses native runners because
the Python backend sidecar is bundled with PyInstaller.

Current release targets:

| Platform | Runner | Target triple | Bundles |
| --- | --- | --- | --- |
| macOS Apple Silicon | `macos-14` | `aarch64-apple-darwin` | `.app` / `.dmg` |
| Linux x64 | `ubuntu-22.04` | `x86_64-unknown-linux-gnu` | `.deb` / `.AppImage` / `.rpm` |
| Windows x64 | `windows-latest` | `x86_64-pc-windows-msvc` | `.msi` / `.exe` |

To create a release, update the app version, commit the change, then push a tag:

```bash
git tag vX.Y.Z
git push origin vX.Y.Z
```

The workflow uploads bundles to a draft GitHub Release for review before
publishing. The distribution page reads the latest public GitHub Release and
links to the matching platform assets.

### Local Build

Build the Python backend sidecar:

```bash
uv run pyinstaller markdown-reader-backend.spec
```

Copy the sidecar binary into the Tauri binary directory. For Apple Silicon macOS:

```bash
cp dist/markdown-reader-backend frontend/src-tauri/binaries/markdown-reader-backend-aarch64-apple-darwin
chmod +x frontend/src-tauri/binaries/markdown-reader-backend-aarch64-apple-darwin
```

For Windows or Linux local builds, use the matching [Rust target triple](https://doc.rust-lang.org/cargo/appendix/glossary.html#target) as the sidecar filename suffix.

Build the desktop bundle:

```bash
cd frontend && npx tauri build --bundles app
```

Output (macOS): `frontend/src-tauri/target/release/bundle/macos/Markdown Reader.app`

### macOS Release Notes

Public macOS downloads need Developer ID signing and Apple notarization to open
without Gatekeeper warnings. If a local beta build is blocked after download, run:

```bash
xattr -dr com.apple.quarantine "/Applications/Markdown Reader.app"
```

For release packaging, use:

```bash
./scripts/package-macos-release.sh
```

---

## AI Provider Configuration

AI features can be configured from the app toolbar through the **Settings** tab
in the AI panel.

Supported providers:

- OpenAI Compatible
- OpenRouter
- OpenAI
- Anthropic

Provider and model preferences are saved per-user in the local app settings
file. API keys are saved through the system credential store when available.

---

## Development

### Setup

```bash
uv sync --extra dev          # install dev dependencies
uv run pre-commit install    # install git hooks
```

### Code quality

```bash
uv run ruff check .          # lint
uv run ruff format --check . # check formatting
uv run ruff format .         # auto-format
```

### Tests

```bash
uv run python -m unittest discover -s tests
uv run python -m unittest tests/test_ai_automation_logic.py  # single file
```

### Frontend build

```bash
cd frontend && npm run build
```

---

## Dependency Management

Python dependencies are managed through `pyproject.toml` and `uv.lock`.
Use `uv sync` for normal setup. If dependencies change, regenerate and commit
the lockfile:

```bash
uv lock
git add pyproject.toml uv.lock && git commit -m "chore: update dependencies"
```

CI runs `uv sync --locked`, so `uv.lock` must stay in sync with
`pyproject.toml`.

Frontend dependencies are managed with npm and `frontend/package-lock.json`.

---

## Documentation

Additional notes live in `docs/`:

- [HostingStrategy.md](docs/HostingStrategy.md)
- [PrepareForMacUser.md](docs/PrepareForMacUser.md)
- [PrepareForWindowsUser.md](docs/PrepareForWindowsUser.md)
- [MathRenderingTestFile.md](docs/MathRenderingTestFile.md)

---

## Contributing

Contributions are welcome. Typical workflow:

```bash
git checkout -b your-branch-name
uv sync --extra dev
cd frontend && npm install && cd ..
uv run pre-commit install
```

Before opening a pull request, run the relevant checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s tests
cd frontend && npm run build
```

Keep changes focused, update documentation when behavior changes, and include
tests for backend or workflow changes where practical.

For more details, see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## License

See [LICENSE](LICENSE.md).
