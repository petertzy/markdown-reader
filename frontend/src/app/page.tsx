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

export default function HomePage() {
  const editor = useEditor();
  const [showPreview] = useState(true);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);

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
        editor.saveFile();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [editor]);

  // "Open file" — uses a hidden file-input because Tauri/browser can't call
  // the native dialog directly without the Tauri API.  In Tauri mode this
  // would be replaced by window.__TAURI__.dialog.open().
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleOpenFile = () => {
    fileInputRef.current?.click();
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    // For browser mode read directly; for Tauri we'd have a native path
    const text = await file.text();
    // In pure browser we don't have an absolute path — use filename as tab label.
    editor.openTextAsTab(file.name, text, null);
    e.target.value = "";
  };

  const handleExport = async (format: "html" | "pdf" | "docx") => {
    try {
      const result = await editor.exportAs(format);
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
        accept=".md,.txt,.html,.pdf"
        className="hidden"
        onChange={handleFileInputChange}
      />

      {/* Toolbar */}
      <div className="relative">
        <Toolbar
          onOpenFile={handleOpenFile}
          onSaveFile={() => editor.saveFile()}
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
