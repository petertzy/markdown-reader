"use client";

/**
 * app/page.tsx
 * ============
 * Main editor page: assembles Toolbar, TabBar, EditorPane,
 * PreviewPane, AIPanel, and StatusBar.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import { useEditor } from "@/hooks/useEditor";
import TabBar from "@/components/TabBar";
import Toolbar from "@/components/Toolbar";
import EditorPane from "@/components/EditorPane";
import PreviewPane from "@/components/PreviewPane";
import AIPanel from "@/components/AIPanel";
import StatusBar from "@/components/StatusBar";
import { Files } from "@/lib/api";

const OPEN_FILE_EXTENSIONS = ["md", "markdown", "txt", "html", "htm", "pdf", "docx"];
const CONVERTIBLE_EXTENSIONS = new Set(["html", "htm", "pdf", "docx"]);

function fileExtension(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function convertedMarkdownLabel(name: string) {
  const withoutExtension = name.replace(/\.[^/.]+$/, "");
  return `${withoutExtension || "converted"}.md`;
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    const chunk = bytes.subarray(i, i + chunkSize);
    binary += String.fromCharCode(...chunk);
  }
  return window.btoa(binary);
}

export default function HomePage() {
  const editor = useEditor();
  const [showPreview] = useState(true);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);

  const handleSaveFile = useCallback(async () => {
    try {
      await editor.saveFile();
    } catch (err) {
      alert(`Save failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [editor]);

  // Load recent files on mount and initialise preview
  useEffect(() => {
    editor.loadRecentFiles();
    if (editor.activeTab.content) {
      editor.refreshPreview(editor.activeTab.content);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Keyboard shortcut: Ctrl/Cmd+S → save
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        void handleSaveFile();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSaveFile]);

  // "Open file" — uses a hidden file-input because Tauri/browser can't call
  // the native dialog directly without the Tauri API.  In Tauri mode this
  // would be replaced by window.__TAURI__.dialog.open().
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isLikelyTauriRuntime =
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window || "__TAURI__" in window || window.navigator.userAgent.includes("Tauri"));

  const handleOpenFile = useCallback(async () => {
    let filePath: string | null = null;

    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        multiple: false,
        filters: [
          { name: "Supported documents", extensions: OPEN_FILE_EXTENSIONS },
          { name: "Markdown", extensions: ["md", "markdown", "txt"] },
          { name: "Convertible documents", extensions: ["html", "htm", "pdf", "docx"] },
        ],
      });
      if (!selected) return;
      filePath = Array.isArray(selected) ? selected[0] : selected;
    } catch {
      // In desktop runtime, avoid browser picker fallback to prevent permission dialogs.
      if (isLikelyTauriRuntime) return;

      // Browser mode fallback.
      fileInputRef.current?.click();
      return;
    }

    if (!filePath) return;

    try {
      await editor.openFile(filePath);
    } catch (err) {
      alert(`Open failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [editor, isLikelyTauriRuntime]);

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const ext = fileExtension(file.name);
      if (CONVERTIBLE_EXTENSIONS.has(ext)) {
        const content_base64 = arrayBufferToBase64(await file.arrayBuffer());
        const { markdown } = await Files.convertToMarkdown({
          filename: file.name,
          content_base64,
        });
        editor.openTextAsTab(convertedMarkdownLabel(file.name), markdown, null, null, true);
      } else {
        // In pure browser we do not have an absolute path, so use filename as tab label.
        const text = await file.text();
        editor.openTextAsTab(file.name, text, null);
      }
    } catch (err) {
      alert(`Open failed: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      e.target.value = "";
    }
  };

  const handleExport = async (format: "html" | "pdf" | "docx") => {
    try {
      let outputPath: string | undefined;
      try {
        const { save } = await import("@tauri-apps/plugin-dialog");
        const extension = format === "pdf" ? "pdf" : format === "docx" ? "docx" : "html";
        const defaultName = `${editor.activeTab.label.replace(/\.[^/.]+$/, "") || "document"}.${extension}`;
        const selected = await save({
          defaultPath: defaultName,
          filters: [{ name: `${extension.toUpperCase()} files`, extensions: [extension] }],
        });
        if (!selected) return;
        outputPath = Array.isArray(selected) ? selected[0] : selected;
      } catch {
        if (format === "html") {
          alert("HTML export requires Tauri desktop app for save dialog. Use the browser download path instead.");
          return;
        }
        alert("PDF/DOCX export requires Tauri desktop app for save dialog.");
        return;
      }
      const result = await editor.exportAs(format, outputPath);
      if (result) {
        alert(`Exported to:\n${result.path}`);
      }
    } catch (err) {
      alert(`Export failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleAIApplyAction = useCallback(
    (type: string, content: string) => {
      if (type === "replace_document") {
        editor.handleContentChange(content);
      } else if (type === "replace_selection") {
        const mono = monacoRef.current;
        if (mono) {
          const sel = mono.getSelection();
          if (sel) {
            mono.executeEdits("ai-replace", [{ range: sel, text: content }]);
          } else {
            editor.handleContentChange(content);
          }
        }
      }
    },
    [editor]
  );

  const getSelectedText = () => {
    const mono = monacoRef.current;
    if (!mono) return "";
    const sel = mono.getSelection();
    if (!sel) return "";
    return mono.getModel()?.getValueInRange(sel) ?? "";
  };

  return (
    <div
      className={`flex flex-col h-screen overflow-hidden ${editor.darkMode ? "dark" : ""}`}
      style={{ background: editor.darkMode ? "#1e1e1e" : "#fff" }}
    >
      {/* Hidden file input for open-file */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".md,.markdown,.txt,.html,.htm,.pdf,.docx"
        className="hidden"
        onChange={handleFileInputChange}
      />

      {/* Toolbar */}
      <div className="relative">
        <Toolbar
          onOpenFile={() => { void handleOpenFile(); }}
          onSaveFile={() => { void handleSaveFile(); }}
          onExport={handleExport}
          onToggleDark={() => editor.setDarkMode((d) => !d)}
          onToggleAIPanel={() => setShowAIPanel((v) => !v)}
          darkMode={editor.darkMode}
          fontSize={editor.fontSize}
          onFontSizeChange={editor.setFontSize}
          showAIPanel={showAIPanel}
        />
        {/* Recent files trigger sits inside a relative container in Toolbar, but
            we render the dropdown here at page level for simplicity */}
      </div>

      {/* Tab bar */}
      <TabBar
        tabs={editor.tabs}
        activeTabId={editor.activeTabId}
        onSelect={(id) => {
          editor.setActiveTabId(id);
          const tab = editor.tabs.find((t) => t.id === id);
          if (tab) editor.refreshPreview(tab.content, tab.filePath ?? undefined);
        }}
        onClose={editor.closeTab}
        onNew={editor.newTab}
      />

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Editor */}
        <EditorPane
          value={editor.activeTab.content}
          onChange={editor.handleContentChange}
          darkMode={editor.darkMode}
          fontSize={editor.fontSize}
          onMount={(e) => { monacoRef.current = e; }}
        />

        {/* Preview */}
        {showPreview && <PreviewPane html={editor.previewHtml} />}

        {/* AI Panel */}
        {showAIPanel && (
          <AIPanel
            documentText={editor.activeTab.content}
            selectedText={getSelectedText()}
            onApplyAction={handleAIApplyAction}
          />
        )}
      </div>

      {/* Status bar */}
      <StatusBar
        stats={editor.wordCount}
        filePath={editor.activeTab.filePath}
        dirty={editor.activeTab.dirty}
      />
    </div>
  );
}
