# Contributing to Markdown Reader

Thank you for your interest in contributing to **Markdown Reader**. Contributions
are welcome, including bug reports, focused feature improvements, tests,
documentation updates, and developer-experience fixes.

---

## About the Project

Markdown Reader is a desktop Markdown editor and reader with:

- a FastAPI backend in `backend/`
- a Next.js frontend and Tauri desktop shell in `frontend/`
- legacy Tkinter app code preserved in `markdown_reader/`
- Python tests in `tests/`
- project notes in `docs/`
- release and distribution workflows in `.github/workflows/`

The current development app runs a local FastAPI backend and launches the Tauri
desktop shell with a Next.js frontend on `http://127.0.0.1:3000`. The helper
uses `http://127.0.0.1:8000` when available, and automatically chooses another
free local port if `8000` is already occupied.

---

## Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for Python dependency management
- Node.js 18 or newer and npm for the frontend
- Rust and the Tauri prerequisites for desktop-shell or packaging work

Docs-only changes usually do not require a full desktop build.

---

## Get Started

1. Fork and clone the repository.

```bash
git clone https://github.com/(your-user-name)/markdown-reader.git
cd markdown-reader
```

2. Create a focused branch.

```bash
git checkout -b <short-description>
```

3. Install Python and frontend dependencies.

```bash
uv sync --extra dev
cd frontend && npm install && cd ..
```

On macOS, PDF export through WeasyPrint also needs Homebrew native libraries:

```bash
brew install glib pango cairo libffi
```

The development helper adds `/opt/homebrew/lib` to
`DYLD_FALLBACK_LIBRARY_PATH` automatically so WeasyPrint can locate
`libgobject-2.0` and related libraries. If those libraries are missing, PDF
export falls back to PyMuPDF with simpler layout.

4. Configure the frontend environment file.

```bash
cp frontend/.env.local.example frontend/.env.local
```

5. Install pre-commit hooks if you plan to commit locally.

```bash
uv run pre-commit install
```

---

## Local Development

Use the project helper for normal desktop development:

```bash
./scripts/dev-tauri.sh
```

This starts the FastAPI backend and launches the Tauri desktop shell. The
backend URL is printed by the script. When it uses the default port, the API
docs are available at:

- Swagger: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

If the script chooses another port, replace `8000` with the printed port. You
can request a specific backend port when needed:

```bash
MARKDOWN_READER_BACKEND_PORT=8010 ./scripts/dev-tauri.sh
```

You can also run services separately when debugging. Use separate terminals for
long-running commands:

```bash
# Terminal 1: backend
uv run uvicorn backend.main:app --host 127.0.0.1 --port 8010 --reload

# Terminal 2: frontend dev server
cd frontend && npm run dev

# Terminal 3: Tauri shell, with the frontend dev server already running
cd frontend && MARKDOWN_READER_BACKEND_PORT=8010 npm run tauri:dev
```

AI-provider features may ask for API keys in the app, but normal documentation,
test, backend, frontend, and onboarding contributions should not require API
keys, secrets, paid services, or authenticated external services.

---

## Validation Checklist

Run the checks that match the files you changed.

### Documentation-only changes

```bash
git diff --check
```

For link or wording updates, also search for stale references that your change
may affect:

```bash
rg -n "old text|old command|old path" README.MD CONTRIBUTING.md docs
```

### Python backend or legacy Python changes

```bash
uv run ruff check .
uv run ruff format --check .
uv run python -m unittest discover -s tests
```

To run one test file:

```bash
uv run python -m unittest tests/test_ai_automation_logic.py
```

### Frontend changes

```bash
cd frontend
npm run build
```

If a frontend lint command is available in your environment, run it as well:

```bash
cd frontend
npm run lint
```

### Desktop or packaging changes

For Tauri or release packaging work, first check the relevant files:

- `frontend/src-tauri/tauri.conf.json`
- `frontend/src-tauri/Cargo.toml`
- `markdown-reader-backend.spec`
- `.github/workflows/release.yml`
- `scripts/dev-tauri.sh`

Then run the smallest local check that proves your change. Full desktop builds
can require platform-specific system packages, so mention any environment gaps
in your pull request.

---

## Docs-Only Contributions

Docs changes are valuable when they make setup, validation, user workflows, or
project architecture easier to understand. Keep them practical:

- update stale commands or paths
- align docs with `README.MD`, `pyproject.toml`, `frontend/package.json`, and
  Tauri config
- add concise troubleshooting notes when you have verified them locally
- avoid broad wording-only rewrites unless the issue specifically asks for one

For broad tracking issues such as `#187`, keep each pull request small and
focused. Prefer one clear improvement, such as contributor onboarding, a setup
note, a feature explanation, a validation checklist, or a small example file.

---

## Issue and Pull Request Etiquette

- Check open issues and pull requests before starting to avoid duplicate work.
- Keep one pull request focused on one problem.
- Describe what changed, why it helps, and how you validated it.
- Include screenshots only when the change affects visible UI or distribution
  pages.
- Do not include secrets, API keys, tokens, or personal credentials in issues,
  commits, logs, screenshots, or pull requests.
- If your change cannot be fully validated locally, explain what you did test
  and what remains unverified.

After review, push your branch and open a pull request from your fork:

```bash
git push origin <new-branch>
```

---

## Code Documentation Guidelines

When creating or updating a Python function, please use clear docstrings for
non-obvious behavior, public helpers, or code paths that are easy to misuse:

```python
"""
[Description of what the function does.]

:param [dateType] [parameterName]: [Description of the parameter.]

:return: A [dataType] [description of the conditions for return.]

:raises [errorType]: If [description of the conditions to raise the error.]
"""
```
