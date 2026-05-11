#!/usr/bin/env bash
# Build a macOS release archive with a valid ad-hoc signature.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="${ROOT}/frontend/src-tauri/target/release/bundle/macos/Markdown Reader.app"
ARTIFACT_DIR="${ROOT}/release-artifacts"
ARTIFACT_PATH="${ARTIFACT_DIR}/Markdown-Reader-2.0.0-macOS-arm64.zip"

if [ ! -d "${APP_PATH}" ]; then
  echo "App bundle not found: ${APP_PATH}" >&2
  echo "Run: cd frontend && npx tauri build --bundles app" >&2
  exit 1
fi

mkdir -p "${ARTIFACT_DIR}"

xattr -cr "${APP_PATH}"

codesign --force --sign - "${APP_PATH}/Contents/MacOS/markdown-reader-backend"
codesign --force --sign - "${APP_PATH}/Contents/MacOS/app"
codesign --force --deep --sign - "${APP_PATH}"
codesign --verify --deep --strict --verbose=4 "${APP_PATH}"

ditto -c -k --keepParent "${APP_PATH}" "${ARTIFACT_PATH}"
shasum -a 256 "${ARTIFACT_PATH}"
