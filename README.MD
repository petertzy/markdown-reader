# Markdown Reader

一個簡潔直觀的 Markdown 閱讀與即時預覽工具，支援黑暗模式與拖放開啟檔案，適用於 macOS 與 Windows 桌面環境。

## 功能特色

-  即時預覽 Markdown 轉換成 HTML
-  黑暗模式切換
-  支援拖放 `.md` 檔案開啟（需要安裝 `tkinterdnd2`）
-  使用簡單、無需編譯
-  純 Python + Tkinter 實作，跨平台

---

## 安裝說明

### 1. 下載專案

```bash
git clone https://github.com/petertzy/markdown-reader.git
cd markdown-reader
```

### 2. 安裝依賴

```bash
pip install markdown2 tkinterdnd2
```

> 💡 macOS 上如遇 `tkinterdnd2` 拖放異常，請考慮使用其 [fork](https://github.com/pmgagne/tkinterDnD2)。

---

## 使用方式

```bash
python3 markdown_reader.py
```

* 打開檔案：從選單「檔案 → 打開檔案」選擇 `.md` 檔
* 拖放開啟：將 `.md` 檔拖入視窗即可
* 黑暗模式：從選單「檢視 → 切換黑暗模式」

---

## 技術細節

* 前端：`tkinter`, `tkinterdnd2`
* Markdown 引擎：`markdown2`
* 即時預覽透過產生臨時 HTML 並於瀏覽器中開啟

---

## 已知問題

* 每次修改文字後會刷新預覽，但不會重複開啟新瀏覽器視窗（已優化）
* macOS 拖放功能需額外注意 `tkinterdnd2` 相容性
* 目前不支援嵌入預覽視窗（未來版本考慮導入 `tkhtmlview`）

---

## 授權

MIT License - 自由使用、修改與散佈。

---

## 貢獻

歡迎提交 pull request 或開 issue，一起改善這個工具！

