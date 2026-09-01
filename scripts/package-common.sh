#!/usr/bin/env bash
# Shared logic for local desktop packaging builds.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_DIR="${ROOT}/frontend"
ARTIFACT_DIR="${ROOT}/release-artifacts"

info() {
  echo "==> $*"
}

warn() {
  echo "WARNING: $*" >&2
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

require_command() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    die "Required command '$cmd' was not found. Install it and retry."
  fi
}

ensure_rust_target() {
  local target="$1"

  if ! command -v rustup >/dev/null 2>&1; then
    die "Rust is required for packaging. Install rustup from https://rustup.rs and retry."
  fi

  if ! rustup target list --installed | grep -Fxq "$target"; then
    info "Installing Rust target ${target}..."
    rustup target add "$target"
  fi
}

ensure_uv() {
  if ! command -v uv >/dev/null 2>&1; then
    die "uv is required for packaging. Install it from https://docs.astral.sh/uv/ and retry."
  fi
}

ensure_node() {
  if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
    die "Node.js and npm are required for packaging. Install Node 20+ and retry."
  fi
}

prepare_linux_system_deps() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    return 0
  fi

  if command -v apt-get >/dev/null 2>&1; then
    info "Ensuring Linux packaging dependencies are installed..."
    local apt_cmd=(apt-get update)
    if command -v sudo >/dev/null 2>&1; then
      apt_cmd=(sudo apt-get update)
    fi
    "${apt_cmd[@]}"

    local install_cmd=(apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf build-essential curl wget file libssl-dev libgtk-3-dev libxdo-dev libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libcairo2 libffi-dev)
    if command -v sudo >/dev/null 2>&1; then
      install_cmd=(sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev patchelf build-essential curl wget file libssl-dev libgtk-3-dev libxdo-dev libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 libcairo2 libffi-dev)
    fi
    "${install_cmd[@]}"
  fi
}

build_backend_sidecar() {
  local target="$1"
  local bin_ext="${2:-}"

  ensure_uv
  info "Syncing Python dependencies with uv..."
  cd "${ROOT}"
  uv sync --frozen

  info "Building backend sidecar with PyInstaller..."
  uv run pyinstaller markdown-reader-backend.spec

  mkdir -p "${FRONTEND_DIR}/src-tauri/binaries"

  local src="${ROOT}/dist/markdown-reader-backend${bin_ext}"
  local dest="${FRONTEND_DIR}/src-tauri/binaries/markdown-reader-backend-${target}${bin_ext}"
  if [[ ! -f "${src}" ]]; then
    die "Backend build output not found at ${src}. The PyInstaller step failed."
  fi

  cp "${src}" "${dest}"
  chmod +x "${dest}" || true

  local default_dest="${FRONTEND_DIR}/src-tauri/binaries/markdown-reader-backend${bin_ext}"
  cp "${src}" "${default_dest}"
  chmod +x "${default_dest}" || true

  info "Backend sidecar staged at ${default_dest}"
}

install_frontend_dependencies() {
  ensure_node
  info "Installing frontend dependencies with npm ci..."
  cd "${FRONTEND_DIR}"
  npm ci
}

run_tauri_build() {
  local target="$1"
  shift

  ensure_node
  if ! command -v cargo >/dev/null 2>&1; then
    die "Cargo is required to build Tauri. Install the Rust toolchain and retry."
  fi

  info "Building Tauri desktop bundle for target ${target}..."
  cd "${FRONTEND_DIR}"
  export NEXT_EXPORT=1
  npx tauri build --target "$target" "$@"
}

collect_release_artifacts() {
  mkdir -p "${ARTIFACT_DIR}"
  local bundle_dir="${FRONTEND_DIR}/src-tauri/target/release/bundle"

  if [[ -d "${bundle_dir}" ]]; then
    info "Collecting packaged artifacts into ${ARTIFACT_DIR}..."
    cp -a "${bundle_dir}"/. "${ARTIFACT_DIR}/"
  else
    warn "No Tauri bundle directory was found under ${bundle_dir}."
    warn "The build may have failed before producing artifacts."
  fi

  # `find` exits successfully even when the directory is empty, so inspect
  # whether it actually returned an entry before claiming success.
  if [[ -n "$(find "${ARTIFACT_DIR}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
    info "Done. Bundles are ready in ${ARTIFACT_DIR}"
  else
    warn "The release-artifacts directory is empty; check the build logs above for errors."
  fi
}

check_run_on_supported_platform() {
  local expected_os="$1"
  local current_os="$(uname -s)"

  case "${expected_os}" in
    linux)
      if [[ "${current_os}" != "Linux" ]]; then
        die "This script must be run on Linux. Detected: ${current_os}"
      fi
      ;;
    darwin)
      if [[ "${current_os}" != "Darwin" ]]; then
        die "This script must be run on macOS. Detected: ${current_os}"
      fi
      ;;
    windows)
      if [[ "${current_os}" != MINGW* && "${current_os}" != MSYS* && "${current_os}" != CYGWIN* && "${current_os}" != "Windows_NT" ]]; then
        die "This script must be run from PowerShell or Git Bash on Windows. Detected: ${current_os}"
      fi
      ;;
  esac
}
