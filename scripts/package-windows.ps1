param(
    [string]$Target = "x86_64-pc-windows-msvc",
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: ./scripts/package-windows.ps1 [-Target <triple>] [-Help]

Build the Windows desktop package for Markdown Reader using the same sidecar + Tauri
workflow as the GitHub Actions release job.

Options:
  -Target <triple>  Override the Rust target triple (default: x86_64-pc-windows-msvc)
  -Help             Show this message and exit
"@
}

if ($Help) {
    Show-Usage
    exit 0
}

$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
$artifacts = Join-Path $root "release-artifacts"

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv is required for packaging. Install it from https://docs.astral.sh/uv/ and retry."
}

if (-not (Get-Command node -ErrorAction SilentlyContinue) -or -not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "Node.js and npm are required for packaging. Install Node 20+ and retry."
}

if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust is required for packaging. Install the Rust toolchain from https://rustup.rs and retry."
}

if (-not (rustup target list --installed | Select-String -SimpleMatch $Target)) {
    Write-Host "==> Installing Rust target $Target..."
    rustup target add $Target
}

Write-Host "==> Syncing Python dependencies with uv..."
Set-Location $root
uv sync --frozen

Write-Host "==> Building backend sidecar with PyInstaller..."
uv run pyinstaller markdown-reader-backend.spec

$binaryDir = Join-Path $frontend "src-tauri\binaries"
New-Item -ItemType Directory -Force -Path $binaryDir | Out-Null

$source = Join-Path $root "dist\markdown-reader-backend.exe"
if (-not (Test-Path $source)) {
    throw "Backend build output not found at $source. The PyInstaller step failed."
}

$targetName = Join-Path $binaryDir ("markdown-reader-backend-{0}.exe" -f $Target)
$defaultName = Join-Path $binaryDir "markdown-reader-backend.exe"
Copy-Item $source $targetName -Force
Copy-Item $source $defaultName -Force

Write-Host "==> Installing frontend dependencies with npm ci..."
Set-Location $frontend
npm ci

Write-Host "==> Building Tauri desktop bundle for target $Target..."
$env:NEXT_EXPORT = "1"
npx tauri build --target $Target

Write-Host "==> Collecting packaged artifacts..."
$bundleDir = Join-Path $frontend "src-tauri\target\release\bundle"
if (Test-Path $bundleDir) {
    New-Item -ItemType Directory -Force -Path $artifacts | Out-Null
    Copy-Item (Join-Path $bundleDir "*") $artifacts -Recurse -Force
    Write-Host "Done. Bundles are ready in $artifacts"
} else {
    throw "No Tauri bundle directory was found under $bundleDir. The build may have failed before producing artifacts."
}

Write-Host "Windows package build completed successfully."
