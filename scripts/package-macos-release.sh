#!/usr/bin/env bash
# Build a macOS release archive.
#
# Public downloads require Developer ID signing and Apple notarization to pass
# Gatekeeper without a warning. Set MACOS_SIGN_IDENTITY to a Developer ID
# Application certificate and provide notarization credentials to create a
# fully trusted package.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_PATH="${ROOT}/frontend/src-tauri/target/release/bundle/macos/Markdown Reader.app"
ARTIFACT_DIR="${ROOT}/release-artifacts"
ARTIFACT_PATH="${ARTIFACT_DIR}/Markdown-Reader-2.0.0-macOS-arm64.zip"
NOTARY_UPLOAD_PATH="${ARTIFACT_DIR}/Markdown-Reader-2.0.0-macOS-arm64-notary.zip"
SIGN_IDENTITY="${MACOS_SIGN_IDENTITY:--}"
SIGN_OPTIONS=()

if [ ! -d "${APP_PATH}" ]; then
  echo "App bundle not found: ${APP_PATH}" >&2
  echo "Run: cd frontend && npx tauri build --bundles app" >&2
  exit 1
fi

mkdir -p "${ARTIFACT_DIR}"

xattr -cr "${APP_PATH}"

if [ "${SIGN_IDENTITY}" != "-" ]; then
  SIGN_OPTIONS=(--options runtime --timestamp)
fi

sign_binary() {
  codesign --force --sign "${SIGN_IDENTITY}" "${SIGN_OPTIONS[@]+"${SIGN_OPTIONS[@]}"}" "$@"
}

sign_binary "${APP_PATH}/Contents/MacOS/markdown-reader-backend"
sign_binary "${APP_PATH}/Contents/MacOS/app"
sign_binary --deep "${APP_PATH}"
codesign --verify --deep --strict --verbose=4 "${APP_PATH}"

if [ "${SIGN_IDENTITY}" != "-" ]; then
  ditto -c -k --keepParent "${APP_PATH}" "${NOTARY_UPLOAD_PATH}"

  if [ -n "${MACOS_NOTARY_PROFILE:-}" ]; then
    xcrun notarytool submit "${NOTARY_UPLOAD_PATH}" \
      --keychain-profile "${MACOS_NOTARY_PROFILE}" \
      --wait
  elif [ -n "${MACOS_NOTARY_APPLE_ID:-}" ] &&
       [ -n "${MACOS_NOTARY_TEAM_ID:-}" ] &&
       [ -n "${MACOS_NOTARY_PASSWORD:-}" ]; then
    xcrun notarytool submit "${NOTARY_UPLOAD_PATH}" \
      --apple-id "${MACOS_NOTARY_APPLE_ID}" \
      --team-id "${MACOS_NOTARY_TEAM_ID}" \
      --password "${MACOS_NOTARY_PASSWORD}" \
      --wait
  else
    echo "Developer ID signing is enabled, but notarization credentials are missing." >&2
    echo "Set MACOS_NOTARY_PROFILE or MACOS_NOTARY_APPLE_ID, MACOS_NOTARY_TEAM_ID, and MACOS_NOTARY_PASSWORD." >&2
    exit 1
  fi

  xcrun stapler staple "${APP_PATH}"
  xcrun stapler validate "${APP_PATH}"
  spctl --assess --type execute --verbose=4 "${APP_PATH}"
else
  echo "Warning: using ad-hoc signing. Downloaded apps will still be blocked by Gatekeeper." >&2
  echo "Set MACOS_SIGN_IDENTITY and notarization credentials for public releases." >&2
fi

ditto -c -k --keepParent "${APP_PATH}" "${ARTIFACT_PATH}"
shasum -a 256 "${ARTIFACT_PATH}"
