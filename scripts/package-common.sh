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

cleanup_macos_dmg_work_files() {
  local target="$1"

  if [[ "$(uname -s)" != "Darwin" ]]; then
    return 0
  fi

  local bundle_dir="${FRONTEND_DIR}/src-tauri/target/${target}/release/bundle"
  local macos_dir="${bundle_dir}/macos"

  if command -v hdiutil >/dev/null 2>&1; then
    while IFS= read -r device_name; do
      if [[ -n "${device_name}" ]]; then
        info "Detaching stale temporary DMG ${device_name}..."
        hdiutil detach "${device_name}" >/dev/null 2>&1 || true
      fi
    done < <(
      hdiutil info | awk -v prefix="${macos_dir}/rw." '
        /^image-path[[:space:]]*:/ {
          image = substr($0, index($0, ":") + 2)
          matched = index(image, prefix) == 1 && image ~ /\.dmg$/
          next
        }
        matched && /^\/dev\/disk[0-9]+[[:space:]]/ {
          print $1
          matched = 0
        }
      '
    )
  fi

  if [[ -d "${macos_dir}" ]]; then
    find "${macos_dir}" -maxdepth 1 -type f -name 'rw.*.dmg' -delete
  fi
}

clean_tauri_bundle_dir() {
  local target="$1"
  local target_bundle_dir="${FRONTEND_DIR}/src-tauri/target/${target}/release/bundle"

  if [[ -d "${target_bundle_dir}" ]]; then
    info "Removing stale Tauri bundle directory ${target_bundle_dir}..."
    rm -rf "${target_bundle_dir}"
  fi
}

collect_release_artifacts() {
  local target="$1"
  local target_artifact_dir="${ARTIFACT_DIR}/${target}"
  mkdir -p "${target_artifact_dir}"
  local target_bundle_dir="${FRONTEND_DIR}/src-tauri/target/${target}/release/bundle"
  local native_bundle_dir="${FRONTEND_DIR}/src-tauri/target/release/bundle"
  local bundle_dir=""

  # Tauri places explicitly targeted builds below target/<triple>. Keep the
  # native path as a fallback for older Tauri versions and native builds.
  for candidate in "${target_bundle_dir}" "${native_bundle_dir}"; do
    if [[ -d "${candidate}" ]] &&
       [[ -n "$(find "${candidate}" -mindepth 1 -maxdepth 1 -print -quit)" ]]; then
      bundle_dir="${candidate}"
      break
    fi
  done

  if [[ -z "${bundle_dir}" ]]; then
    die "No packaged artifacts found for target ${target}; checked ${target_bundle_dir} and ${native_bundle_dir}."
  fi

  info "Collecting packaged artifacts from ${bundle_dir} into ${target_artifact_dir}..."
  find "${target_artifact_dir}" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  cp -a "${bundle_dir}"/. "${target_artifact_dir}/"
  find "${target_artifact_dir}" -type f -name 'rw.*.dmg' -delete
  info "Done. Bundles are ready in ${target_artifact_dir}"
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
