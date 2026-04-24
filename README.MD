# Markdown Reader

<img width="1320" height="723" alt="Image" src="https://github.com/user-attachments/assets/01271258-68f1-4b34-ae08-c94daf80af43" />

---

Modern Markdown editor with a Next.js UI, FastAPI backend, AI features, and desktop packaging via Tauri.

Planning notes: [scripts/ProjectPlan.md](scripts/ProjectPlan.md)

---

## Current Architecture

### Development mode

- Launches a real Tauri desktop window instead of a browser tab
- Frontend still runs from the Next.js dev server on `http://localhost:3000`
- Backend runs from the FastAPI dev server on `http://127.0.0.1:8000`
- Recommended start command: `./scripts/dev-tauri.sh`
- In this mode, the Tauri shell talks to the fixed dev backend on port `8000`
- The packaged Python sidecar is not used in debug mode

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
├── scripts/dev-tauri.sh        # Recommended native dev startup
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
./scripts/dev-tauri.sh
```

Open:

- Backend docs: http://127.0.0.1:8000/docs
- Tauri native app window: launched automatically by `./scripts/dev-tauri.sh`

### 4) Stop services

Press `Ctrl+C` in the terminal running `./scripts/dev-tauri.sh`.

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

<img width="264" height="139" alt="Image" src="https://github.com/user-attachments/assets/18091038-758b-40cd-ad1f-08700a4e8b92" />

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
