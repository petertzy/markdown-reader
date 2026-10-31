# Technical Documentation

This file contains the advanced technical details for Markdown Reader. It is
linked from the main [README](../README.MD), which is kept focused on the
project's purpose, installation, configuration, and basic usage.

## Table of Contents

- [Architecture](#architecture)
  - [Local Backend Security](#local-backend-security)
  - [Desktop Content Security Policy](#desktop-content-security-policy)
- [PDF Export Dependencies](#pdf-export-dependencies)
  - [macOS PDF Export Dependencies](#macos-pdf-export-dependencies)
  - [Windows PDF Export Dependencies](#windows-pdf-export-dependencies)
- [Build Release Artifacts Locally](#build-release-artifacts-locally)

## Architecture

Markdown Reader is split into three main layers to ensure maximum performance and maintainability:

1. **Backend (`/backend`)**: A blazing-fast FastAPI application handling rendering, export, and all AI API communications.
2. **Frontend (`/frontend`)**: A Next.js UI providing the rich editor experience, packaged within a Tauri desktop shell.
When packaged for desktop use, the Python backend is bundled as a silent Tauri sidecar process, dynamically assigning ports at runtime to avoid conflicts. In development, `./scripts/dev-tauri.sh` uses the same port-handoff path when it needs to avoid a local port conflict.

### Local Backend Security

The packaged desktop sidecar generates a random authentication token for every
launch. All of its API requests must include that token; it is held in memory
only and is not written to disk. The standalone development backend remains
unauthenticated by default for local development. Set
`MARKDOWN_READER_BACKEND_TOKEN` before starting it to require the same request
header (`X-Markdown-Reader-Token`). Tauri development mode forwards that token
from Rust without exposing it to WebView JavaScript. For browser-only
development, set `NEXT_PUBLIC_BACKEND_TOKEN` to the same value.

### Desktop Content Security Policy

The packaged Tauri WebView uses a default-deny policy and permits network
connections only to the app origin and the loopback backend. `object-src` is
disabled and `base-uri` is restricted to the application origin.

`script-src 'unsafe-inline'` remains necessary because a Next.js static export
embeds its hydration payload as inline scripts; static files cannot receive a
per-request nonce. `style-src 'unsafe-inline'` remains necessary for React UI
layout updates and the isolated Markdown preview's inline styles. Monaco loads
its editor workers from `blob:`, so `worker-src` explicitly allows `blob:`.
Monaco assets are copied from the installed dependency into `public/monaco`
before development and production builds and loaded from `/monaco/vs`, without
contacting a CDN. `wasm-unsafe-eval` is currently retained pending a separate
packaged-runtime audit; the editor loading failure was caused by the default
CDN loader, not evidence of a WebAssembly requirement. The policy does not permit the
broader JavaScript `unsafe-eval` directive. Remote `http:` and `https:` image
sources remain available only for images referenced by Markdown previews.

## PDF Export Dependencies

### macOS PDF Export Dependencies

PDF export uses WeasyPrint when its native libraries are available. On macOS,
install the Homebrew libraries below so WeasyPrint can find `libgobject-2.0`,
Pango, and Cairo:

```bash
brew install glib pango cairo libffi
```

`./scripts/dev-tauri.sh` automatically adds `/opt/homebrew/lib` to
`DYLD_FALLBACK_LIBRARY_PATH` for Apple Silicon Homebrew installs. If WeasyPrint
is unavailable, Markdown Reader falls back to PyMuPDF so PDF export can still
complete, but WeasyPrint generally provides better layout fidelity.

For a fuller walkthrough of the macOS dependencies, including shell configuration, see [PrepareForMacUser.md](./PrepareForMacUser.md).

### Windows PDF Export Dependencies

On Windows, WeasyPrint requires native system libraries (Cairo, Pango) that are not available by default. Install them via MSYS2 by following the steps in [PrepareForWindowsUser.md](./PrepareForWindowsUser.md).

If WeasyPrint is unavailable, PDF export falls back to PyMuPDF with simpler layout, the same as on macOS.

## Build Release Artifacts Locally

To package the desktop app without using GitHub Actions, run the platform-specific helper from the project root:

```bash
# Linux
./scripts/package-linux.sh

# macOS
./scripts/package-macos.sh

# Windows (PowerShell)
./scripts/package-windows.ps1
```

Each script stages the Python backend sidecar, installs the frontend dependencies, runs the matching Tauri release build, and copies the final bundle(s) into `release-artifacts/<target>/` for easy distribution.

On macOS, the default command builds the `.app` bundle. To also build a DMG installer, run:

```bash
./scripts/package-macos.sh --dmg
```

To explicitly set a build target:

```bash
# Linux x64
./scripts/package-linux.sh --target x86_64-unknown-linux-gnu

# macOS Apple Silicon
./scripts/package-macos.sh --target aarch64-apple-darwin

# Windows x64
./scripts/package-windows.ps1 -Target x86_64-pc-windows-msvc
```

To see platform-specific options:

```bash
# Linux
./scripts/package-linux.sh --help

# macOS
./scripts/package-macos.sh --help

# Windows (PowerShell)
./scripts/package-windows.ps1 -Help
```
