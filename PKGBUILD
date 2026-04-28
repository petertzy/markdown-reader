pkgname=markdown-reader
pkgver=0.0.1
pkgrel=1
pkgdesc="Modern Markdown editor with a Next.js UI, FastAPI backend, AI features, and desktop packaging via Tauri"
arch=('any')
url=""
license=('MIT')
groups=()
depends=(
    'python'
)

build() {
    cd "$srcdir/../frontend"
    npm install
    npm install -D @tauri-apps/cli @tauri-apps/api
    cd ..
    uv run pyinstaller -F -n markdown-reader-backend backend/main.py
    mkdir frontend/src-tauri/binaries
    cp dist/markdown-reader-backend frontend/src-tauri/binaries/markdown-reader-backend-x86_64-unknown-linux-gnu
    chmod +x frontend/src-tauri/binaries/markdown-reader-backend-x86_64-unknown-linux-gnu
    cd frontend
    export NO_STRIP=true
    npx tauri build --bundles appimage --target ../pkg
}