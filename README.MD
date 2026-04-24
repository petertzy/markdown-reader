# Markdown Reader

Modern Markdown editor with a Next.js UI, FastAPI backend, AI features, and desktop packaging via Tauri.

Planning notes: [scripts/ProjectPlan.md](scripts/ProjectPlan.md)

---

## Current Architecture

### Development mode

- Frontend: Next.js on `http://localhost:3000`
- Backend: FastAPI on `http://127.0.0.1:8000`
- Recommended start command: `./scripts/dev.sh`

### Desktop (packaged) mode

- Users launch one app only: `Markdown Reader.app`
- Python backend is bundled as a sidecar process
- Backend port is dynamically assigned by the OS at runtime (no hard-coded 8000/3000 in desktop mode)
- Frontend discovers backend port through a Tauri command

This avoids port collisions with local services and allows multiple app instances more safely.

---

## Repository Layout

```text
MarkdownReader/
├── backend/                    # FastAPI app and routers
├── frontend/                   # Next.js + Tauri desktop shell
├── markdown_reader/            # Existing Python business logic (preserved)
├── scripts/dev.sh              # One-command dev startup
├── tests/                      # Unit/integration tests
├── README_OLD.MD               # Legacy tkinter-era documentation
└── pyproject.toml
```

---

## Quick Start (Development)

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv)
- Node.js 18+

### 1) Install dependencies

```bash
uv sync
cd frontend && npm install
```

> **Note for contributors:** `pre-commit` is required for git hooks (code linting/formatting runs on every commit).
> If you see `No module named pre_commit` when committing, run:
>
> ```bash
> uv add --dev pre-commit
> uv run pre-commit install
> ```

### 2) Configure frontend env

```bash
cp frontend/.env.local.example frontend/.env.local
```

### 3) Start services

```bash
./scripts/dev.sh
```

Open:

- Frontend: http://localhost:3000
- Backend docs: http://127.0.0.1:8000/docs

### 4) Stop services

Press `Ctrl+C` in the terminal running `./scripts/dev.sh`.

---

## Desktop Build (Single App)

The desktop build produces one user-facing app and bundles the backend internally.

### 1) Install Tauri toolchain

Follow OS prerequisites:

- https://tauri.app/start/prerequisites/

Install frontend tooling:

```bash
cd frontend
npm install
npm install -D @tauri-apps/cli @tauri-apps/api
```

### 2) Build backend sidecar executable

```bash
cd ..
uv run pyinstaller -F -n markdown-reader-backend backend/main.py
```

### 3) Copy sidecar binary into Tauri

For Apple Silicon macOS:

```bash
cp dist/markdown-reader-backend frontend/src-tauri/binaries/markdown-reader-backend-aarch64-apple-darwin
chmod +x frontend/src-tauri/binaries/markdown-reader-backend-aarch64-apple-darwin
```

For other targets, use the corresponding Rust target-triple suffix.

### 4) Build the desktop app

```bash
cd frontend
npx tauri build --bundles app
```

Output path (macOS):

- `frontend/src-tauri/target/release/bundle/macos/Markdown Reader.app`

---

## API Surface (Backend)

Main groups:

- `/api/files/*`
- `/api/markdown/*`
- `/api/ai/*`
- `/api/export/*`

Health endpoint:

- `GET /api/health`

Interactive docs (dev mode):

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

---

## Notes About Ports

- In development mode, fixed ports (`3000` and `8000`) are used for convenience.
- In packaged desktop mode, backend uses a dynamically assigned local port.
- This is intentional and follows common desktop-app sidecar practices.

---

## Legacy UI

The old tkinter entrypoint is preserved:

```bash
uv run python app.py
```

Legacy docs: [README_OLD.MD](README_OLD.MD)
