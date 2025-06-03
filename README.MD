# Markdown Reader

一個簡潔直觀的 Markdown 閱讀與即時預覽工具，支援黑暗模式與拖放開啟檔案，適用於 macOS 與 Windows 桌面環境。

## 功能特色

- ✅ 即時預覽 Markdown 轉換成 HTML
- 🌙 黑暗模式切換
- 🖱️ 支援拖放 `.md` 檔案開啟（需安裝 `tkinterdnd2`）
- 💻 純 Python + Tkinter 實作，跨平台
- 📦 支援打包為 macOS 應用程式（使用 `py2app`）
- 🧩 自動預覽且只開啟一次預覽視窗，體驗更佳

---

## 安裝與使用方式

### 1. 下載專案

```bash
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader
```

### 2. 建立虛擬環境（推薦）

```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# .\venv\Scripts\activate  # Windows（cmd/powershell）
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

💡 macOS 如遇拖放無效，請改用 [tkinterDnD2 fork](https://github.com/pmgagne/tkinterDnD2)。

---

## 執行程式

```bash
python markdown_reader.py
```

### 使用說明

* 📂 開啟檔案：從選單「檔案 → 打開檔案」選擇 `.md` 檔
* 🖱️ 拖放開啟：將 `.md` 檔直接拖入視窗
* 🌙 黑暗模式：從選單「檢視 → 切換黑暗模式」
* 🌐 預覽視窗：會自動開啟瀏覽器顯示 Markdown 預覽，不會重複開啟

---

## 打包為 macOS 應用程式（可選）

若要將本程式打包為 `.app`，請安裝 `py2app` 並建立 `setup.py`：

### 安裝 py2app

```bash
pip install py2app
```

### 建立 `setup.py`

```python
from setuptools import setup

APP = ['markdown_reader.py']
OPTIONS = {
    'argv_emulation': True,
    'includes': ['markdown2', 'tkinterdnd2'],
    'iconfile': 'icon.icns',  # 可選圖示
}

setup(
    app=APP,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
```

### 執行打包

```bash
python setup.py py2app
```

生成的應用會出現在 `dist/` 資料夾，雙擊即可啟動。

---

## 技術細節

* GUI：`tkinter`、`tkinterdnd2`
* Markdown 引擎：`markdown2`
* HTML 預覽：動態生成 HTML，並自動在瀏覽器中開啟
* 支援拖放、即時刷新，但避免重複開啟瀏覽器頁籤

---

## 授權 License

本專案以 MIT 授權釋出，可自由使用、修改、分發。

---

## 貢獻方式

歡迎任何形式的貢獻，包括：

* Bug 回報
* 功能建議
* Pull Request
* 文檔優化

