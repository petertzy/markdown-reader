#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/package-common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/package-macos.sh [--target <triple>] [--help]

Build the macOS desktop package for Markdown Reader using the same sidecar + Tauri
workflow as the release pipeline.

Options:
  --target <triple>  Override the Rust target triple (default: detected architecture)
  --help             Show this message and exit
EOF
}

TARGET="${MARKDOWN_READER_TARGET:-}"
if [[ -z "${TARGET}" ]]; then
  case "$(uname -m)" in
    arm64)
      TARGET="aarch64-apple-darwin"
      ;;
    x86_64)
      TARGET="x86_64-apple-darwin"
      ;;
    *)
      die "Unsupported macOS architecture '$(uname -m)'. Supported values are arm64 and x86_64."
      ;;
  esac
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target)
      TARGET="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      die "Unknown option: $1"
      ;;
  esac
done

check_run_on_supported_platform darwin
if ! xcode-select -p >/dev/null 2>&1; then
  die "Xcode Command Line Tools are required for macOS packaging. Run 'xcode-select --install' and retry."
fi

ensure_rust_target "$TARGET"
build_backend_sidecar "$TARGET"
install_frontend_dependencies
run_tauri_build "$TARGET"
collect_release_artifacts "$TARGET"

info "macOS package build completed successfully."
