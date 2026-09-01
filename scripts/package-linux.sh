#!/usr/bin/env bash
set -euo pipefail

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/package-common.sh"

usage() {
  cat <<'EOF'
Usage: ./scripts/package-linux.sh [--target <triple>] [--help]

Build the Linux desktop package for Markdown Reader using the same Tauri + PyInstaller
steps as the GitHub Actions release workflow.

Options:
  --target <triple>  Override the Rust target triple (default: x86_64-unknown-linux-gnu)
  --help             Show this message and exit
EOF
}

TARGET="x86_64-unknown-linux-gnu"

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

check_run_on_supported_platform linux
prepare_linux_system_deps
ensure_rust_target "$TARGET"
build_backend_sidecar "$TARGET"
install_frontend_dependencies
run_tauri_build "$TARGET"
collect_release_artifacts

info "Linux package build completed successfully."
