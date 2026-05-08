"use client";

/**
 * app/page.tsx
 * ============
 * Main editor page: assembles Toolbar, TabBar, EditorPane,
 * PreviewPane, AIPanel, and StatusBar.
 */

import { useState, useRef, useEffect, useCallback, useMemo } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import { useEditor } from "@/hooks/useEditor";
import TabBar from "@/components/TabBar";
import Toolbar from "@/components/Toolbar";
import MenuBar, { type MenuGroup } from "@/components/MenuBar";
import EditorPane from "@/components/EditorPane";
import PreviewPane from "@/components/PreviewPane";
import SplitPane from "@/components/SplitPane";
import AIPanel from "@/components/AIPanel";
import StatusBar from "@/components/StatusBar";
import { Export, Files, getBaseUrl, type ExportPayload } from "@/lib/api";
import {
  resolveShortcutDefinitions,
  shortcutMatchesEvent,
  isEditableTarget,
  type ActionId,
} from "@/lib/keyboardShortcuts";

const OPEN_FILE_EXTENSIONS = ["md", "markdown", "txt", "html", "htm", "pdf", "docx"];
const CONVERTIBLE_EXTENSIONS = new Set(["html", "htm", "pdf", "docx"]);
const SUPPORTED_FILE_EXTENSIONS = new Set(OPEN_FILE_EXTENSIONS);

function fileExtension(name: string) {
  return name.split(".").pop()?.toLowerCase() ?? "";
}

function isSupportedFile(name: string) {
  return SUPPORTED_FILE_EXTENSIONS.has(fileExtension(name));
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

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function isLikelyDesktopRuntime() {
  return (
    typeof window !== "undefined" &&
    ("__TAURI_INTERNALS__" in window ||
      "__TAURI__" in window ||
      window.location.hostname === "tauri.localhost" ||
      window.navigator.userAgent.includes("Tauri"))
  );
}

export default function HomePage() {
  const editor = useEditor();
  const [showPreview] = useState(true);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const [isLikelyTauriRuntime, setIsLikelyTauriRuntime] = useState(false);
  const [backendStatus, setBackendStatus] = useState<"starting" | "ready" | "error">("ready");
  const [backendMessage, setBackendMessage] = useState<string | null>(null);
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const dragCounterRef = useRef(0);
  const openFileRef = useRef(editor.openFile);
  const openTextAsTabRef = useRef(editor.openTextAsTab);
  const lastDroppedPathsRef = useRef<{ signature: string; at: number } | null>(null);

  const handleSaveFile = useCallback(async () => {
    try {
      await editor.saveFile();
    } catch (err) {
      alert(`Save failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [editor]);

  const runMonacoAction = useCallback((actionId: string) => {
    const mono = monacoRef.current;
    if (!mono) return;
    mono.focus();
    mono.trigger("keyboard-shortcut", actionId, null);
  }, []);

  const replaceSelection = useCallback(
    (source: string, transform: (selectedText: string) => { text: string; cursorOffset?: number }) => {
      const mono = monacoRef.current;
      const selection = mono?.getSelection();
      const model = mono?.getModel();
      if (!mono || !selection || !model) return;

      const selectedText = selection.isEmpty() ? "" : model.getValueInRange(selection);
      const { text, cursorOffset } = transform(selectedText);
      const startOffset = model.getOffsetAt(selection.getStartPosition());
      mono.executeEdits(source, [{ range: selection, text, forceMoveMarkers: true }]);
      if (selection.isEmpty() && typeof cursorOffset === "number") {
        mono.setPosition(model.getPositionAt(startOffset + cursorOffset));
      }
      mono.focus();
    },
    []
  );

  const wrapSelection = useCallback(
    (source: string, before: string, after = before) => {
      replaceSelection(source, (selectedText) => ({
        text: `${before}${selectedText}${after}`,
        cursorOffset: before.length,
      }));
    },
    [replaceSelection]
  );

  const applyHeading = useCallback(
    (level: 0 | 1 | 2 | 3) => {
      replaceSelection("heading", (selectedText) => {
        const content = selectedText || "Heading";
        const hashes = level === 0 ? "" : `${"#".repeat(level)} `;
        const normalized = content
          .split("\n")
          .map((line) => `${hashes}${line.replace(/^#{1,6}\s+/, "")}`)
          .join("\n");
        return { text: normalized, cursorOffset: normalized.length };
      });
    },
    [replaceSelection]
  );

  const insertTable = useCallback(() => {
    replaceSelection("insert-table", () => ({
      text: "| Column 1 | Column 2 | Column 3 |\n| --- | --- | --- |\n| Cell | Cell | Cell |",
    }));
  }, [replaceSelection]);

  // Warm the packaged sidecar on mount so the first user action is not silent.
  useEffect(() => {
    let cancelled = false;
    const detectedTauriRuntime = isLikelyDesktopRuntime();
    setIsLikelyTauriRuntime(detectedTauriRuntime);

    async function initialiseBackend() {
      try {
        if (detectedTauriRuntime) {
          setBackendStatus("starting");
          await getBaseUrl();
        }
        if (cancelled) return;
        setBackendStatus("ready");
        setBackendMessage(null);
        await editor.loadRecentFiles();
        if (!cancelled && editor.activeTab.content) {
          editor.refreshPreview(editor.activeTab.content);
        }
      } catch (err) {
        console.error(err);
        if (!cancelled) {
          setBackendStatus("error");
          setBackendMessage(err instanceof Error ? err.message : String(err));
        }
      }
    }

    void initialiseBackend();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // "Open file" — uses a hidden file-input because Tauri/browser can't call
  // the native dialog directly without the Tauri API.  In Tauri mode this
  // would be replaced by window.__TAURI__.dialog.open().
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleOpenFile = useCallback(async () => {
    if (isLikelyTauriRuntime && backendStatus !== "ready") return;

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
  }, [backendStatus, editor, isLikelyTauriRuntime]);

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

  const handleExport = useCallback(async (format: "html" | "pdf" | "docx") => {
    try {
      let outputPath: string | undefined;
      const extension = format === "pdf" ? "pdf" : format === "docx" ? "docx" : "html";
      const defaultName = `${editor.activeTab.label.replace(/\.[^/.]+$/, "") || "document"}.${extension}`;

      try {
        const { save } = await import("@tauri-apps/plugin-dialog");
        const selected = await save({
          defaultPath: defaultName,
          filters: [{ name: `${extension.toUpperCase()} files`, extensions: [extension] }],
        });
        if (!selected) return;
        outputPath = Array.isArray(selected) ? selected[0] : selected;
      } catch {
        if (format === "html") {
          const payload: ExportPayload = {
            content: editor.activeTab.content,
            base_dir: editor.activeTab.filePath?.replace(/[^/\\]+$/, ""),
            dark_mode: editor.darkMode,
            font_size: editor.fontSize,
          };
          const blob = await Export.downloadHtml(payload);
          downloadBlob(blob, defaultName);
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
  }, [editor]);

  const actions = useMemo<Record<ActionId, () => void>>(
    () => ({
      "file.new": editor.newTab,
      "file.open": () => { void handleOpenFile(); },
      "file.save": () => { void handleSaveFile(); },
      "file.closeTab": () => editor.closeTab(editor.activeTabId),
      "file.closeAllTabs": editor.closeAllTabs,
      "file.exportHtml": () => { void handleExport("html"); },
      "file.exportPdf": () => { void handleExport("pdf"); },
      "file.exportDocx": () => { void handleExport("docx"); },
      "edit.undo": () => runMonacoAction("undo"),
      "edit.redo": () => runMonacoAction("redo"),
      "edit.search": () => runMonacoAction("actions.find"),
      "edit.replace": () => runMonacoAction("editor.action.startFindReplaceAction"),
      "format.bold": () => wrapSelection("bold", "**"),
      "format.italic": () => wrapSelection("italic", "*"),
      "format.underline": () => wrapSelection("underline", "<u>", "</u>"),
      "format.heading1": () => applyHeading(1),
      "format.heading2": () => applyHeading(2),
      "format.heading3": () => applyHeading(3),
      "format.normal": () => applyHeading(0),
      "table.insert": insertTable,
      "view.toggleDarkMode": () => editor.setDarkMode((dark) => !dark),
      "view.toggleAIPanel": () => setShowAIPanel((visible) => !visible),
    }),
    [
      applyHeading,
      editor,
      handleOpenFile,
      handleExport,
      handleSaveFile,
      insertTable,
      runMonacoAction,
      wrapSelection,
    ]
  );

  const shortcuts = useMemo(() => resolveShortcutDefinitions(), []);
  const backendDisabled = backendStatus !== "ready";

  const menuGroups = useMemo<MenuGroup[]>(
    () => [
      {
        label: "File",
        items: [
          { id: "file.new", label: "New", onSelect: actions["file.new"] },
          { id: "file.open", label: "Open File", onSelect: actions["file.open"], disabled: backendDisabled },
          { id: "file.save", label: "Save File", onSelect: actions["file.save"], disabled: backendDisabled },
          "separator",
          { id: "file.exportHtml", label: "Export to HTML", onSelect: actions["file.exportHtml"], disabled: backendDisabled },
          { id: "file.exportDocx", label: "Export to Word", onSelect: actions["file.exportDocx"], disabled: backendDisabled },
          { id: "file.exportPdf", label: "Export to PDF", onSelect: actions["file.exportPdf"], disabled: backendDisabled },
          "separator",
          { id: "file.closeTab", label: "Close", onSelect: actions["file.closeTab"] },
          { id: "file.closeAllTabs", label: "Close All", onSelect: actions["file.closeAllTabs"] },
        ],
      },
      {
        label: "Edit",
        items: [
          { id: "edit.undo", label: "Undo", onSelect: actions["edit.undo"] },
          { id: "edit.redo", label: "Redo", onSelect: actions["edit.redo"] },
          "separator",
          { id: "edit.search", label: "Search...", onSelect: actions["edit.search"] },
          { id: "edit.replace", label: "Replace...", onSelect: actions["edit.replace"] },
        ],
      },
      {
        label: "Format",
        items: [
          { id: "format.bold", label: "Bold", onSelect: actions["format.bold"] },
          { id: "format.italic", label: "Italic", onSelect: actions["format.italic"] },
          { id: "format.underline", label: "Underline", onSelect: actions["format.underline"] },
          "separator",
          { id: "format.heading1", label: "Heading 1", onSelect: actions["format.heading1"] },
          { id: "format.heading2", label: "Heading 2", onSelect: actions["format.heading2"] },
          { id: "format.heading3", label: "Heading 3", onSelect: actions["format.heading3"] },
          { id: "format.normal", label: "Normal Text", onSelect: actions["format.normal"] },
        ],
      },
      {
        label: "View",
        items: [
          { id: "view.toggleDarkMode", label: "Toggle Dark Mode", onSelect: actions["view.toggleDarkMode"] },
          { id: "view.toggleAIPanel", label: "Show AI Agent Panel", onSelect: actions["view.toggleAIPanel"] },
        ],
      },
      {
        label: "Table",
        items: [{ id: "table.insert", label: "Insert Table...", onSelect: actions["table.insert"] }],
      },
      {
        label: "Shortcuts",
        items: shortcuts.map((shortcut) => ({
          id: shortcut.id,
          label: shortcut.label,
          onSelect: actions[shortcut.id],
        })),
      },
    ],
    [actions, backendDisabled, shortcuts]
  );

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const editableTarget = isEditableTarget(event.target);
      const isMonacoTarget =
        event.target instanceof HTMLElement && Boolean(event.target.closest(".monaco-editor"));

      for (const shortcut of shortcuts) {
        const matches = shortcut.bindings.some((binding) => shortcutMatchesEvent(binding, event));
        if (!matches) continue;
        if (shortcut.scope === "editor" && editableTarget && !isMonacoTarget) return;

        event.preventDefault();
        actions[shortcut.id]();
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [actions, shortcuts]);

  const handleAIApplyAction = useCallback(
    (type: string, content: string) => {
      if (type === "replace_document") {
        editor.handleContentChange(content);
      } else if (type === "insert_below_document") {
        const currentContent = editor.activeTab.content;
        const separator = currentContent.endsWith("\n") ? "\n" : "\n\n";
        editor.handleContentChange(`${currentContent}${separator}${content}`);
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
      } else if (type === "insert_below_selection" || type === "insert_below") {
        const mono = monacoRef.current;
        const model = mono?.getModel();
        const sel = mono?.getSelection();
        if (mono && model && sel && !sel.isEmpty()) {
          const selectedText = model.getValueInRange(sel);
          const separator = selectedText.endsWith("\n") ? "\n" : "\n\n";
          const range = {
            startLineNumber: sel.endLineNumber,
            startColumn: sel.endColumn,
            endLineNumber: sel.endLineNumber,
            endColumn: sel.endColumn,
          };
          mono.executeEdits("ai-insert-below", [
            { range, text: `${separator}${content}` },
          ]);
        } else {
          const currentContent = editor.activeTab.content;
          const separator = currentContent.endsWith("\n") ? "\n" : "\n\n";
          editor.handleContentChange(`${currentContent}${separator}${content}`);
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

  useEffect(() => {
    openFileRef.current = editor.openFile;
    openTextAsTabRef.current = editor.openTextAsTab;
  }, [editor.openFile, editor.openTextAsTab]);

  const openDroppedPaths = useCallback(
    async (paths: string[]) => {
      const supportedPaths = paths.filter(isSupportedFile);
      if (supportedPaths.length === 0) return;

      const signature = supportedPaths.join("\n");
      const previousDrop = lastDroppedPathsRef.current;
      const now = Date.now();
      if (previousDrop?.signature === signature && now - previousDrop.at < 750) return;
      lastDroppedPathsRef.current = { signature, at: now };

      for (const path of supportedPaths) {
        try {
          await openFileRef.current(path);
        } catch (err) {
          alert(`Open failed: ${err instanceof Error ? err.message : String(err)}`);
        }
      }
    },
    []
  );

  useEffect(() => {
    if (!isLikelyTauriRuntime) return;

    let cancelled = false;
    let unlisten: (() => void) | null = null;

    import("@tauri-apps/api/webview")
      .then(({ getCurrentWebview }) =>
        getCurrentWebview().onDragDropEvent((event) => {
          if (event.payload.type === "drop") {
            void openDroppedPaths(event.payload.paths);
          }
        })
      )
      .then((cleanup) => {
        if (cancelled) {
          cleanup();
        } else {
          unlisten = cleanup;
        }
      })
      .catch(console.error);

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [isLikelyTauriRuntime, openDroppedPaths]);

  useEffect(() => {
    if (!isLikelyTauriRuntime) return;

    let cancelled = false;
    let unlisten: (() => void) | null = null;
    const openPaths = (paths: string[]) => {
      if (paths.length > 0) {
        void openDroppedPaths(paths);
      }
    };

    import("@tauri-apps/api/event")
      .then(({ listen }) => listen<string[]>("open-file-paths", (event) => openPaths(event.payload)))
      .then((cleanup) => {
        if (cancelled) {
          cleanup();
        } else {
          unlisten = cleanup;
        }
        return import("@tauri-apps/api/core");
      })
      .then(({ invoke }) => invoke<string[]>("take_pending_open_files"))
      .then((paths) => {
        if (!cancelled) openPaths(paths);
      })
      .catch(console.error);

    return () => {
      cancelled = true;
      unlisten?.();
    };
  }, [isLikelyTauriRuntime, openDroppedPaths]);

  // ── Drag-and-drop file handling ────────────────────────────────────────────
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current += 1;
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragCounterRef.current -= 1;
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "copy";
  }, []);

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      dragCounterRef.current = 0;

      const files = Array.from(e.dataTransfer.files);

      if (files.length === 0) return;

      // In Tauri mode, the native webview event is the reliable source of paths.
      // Keep this fallback for runtimes that still expose a File.path value.
      if (isLikelyTauriRuntime) {
        const paths = files
          .map((file) => (file as File & { path?: string }).path)
          .filter((path): path is string => Boolean(path));
        await openDroppedPaths(paths);
        return;
      } else {
        // Browser mode — read file contents
        for (const file of files) {
          if (!isSupportedFile(file.name)) continue;

          const ext = fileExtension(file.name);
          if (CONVERTIBLE_EXTENSIONS.has(ext)) {
            try {
              const content_base64 = arrayBufferToBase64(await file.arrayBuffer());
              const { markdown } = await Files.convertToMarkdown({
                filename: file.name,
                content_base64,
              });
              openTextAsTabRef.current(convertedMarkdownLabel(file.name), markdown, null, null, true);
            } catch (err) {
              alert(`Open failed: ${err instanceof Error ? err.message : String(err)}`);
            }
          } else {
            try {
              const text = await file.text();
              openTextAsTabRef.current(file.name, text, null);
            } catch (err) {
              alert(`Open failed: ${err instanceof Error ? err.message : String(err)}`);
            }
          }
        }
      }
    },
    [isLikelyTauriRuntime, openDroppedPaths]
  );

  return (
    <div
      className={`flex flex-col h-screen overflow-hidden ${editor.darkMode ? "dark" : ""}`}
      style={{ background: editor.darkMode ? "#1e1e1e" : "#fff" }}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
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
      <MenuBar groups={menuGroups} shortcuts={shortcuts} />
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
          backendStatus={backendStatus}
          backendMessage={backendMessage}
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
        <SplitPane
          left={
            <EditorPane
              value={editor.activeTab.content}
              onChange={editor.handleContentChange}
              darkMode={editor.darkMode}
              fontSize={editor.fontSize}
              onMount={(e) => { monacoRef.current = e; }}
            />
          }
          right={
            showPreview ? (
              <PreviewPane
                html={editor.previewHtml}
                loading={isLikelyTauriRuntime && backendStatus === "starting"}
                error={backendStatus === "error" ? backendMessage : null}
              />
            ) : null
          }
        />

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
