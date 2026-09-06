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
import { useSlashCommands, isSlashTriggerPosition, type SlashCommand } from "@/hooks/useSlashCommands";
import { useFileIO } from "@/hooks/useFileIO";
import { useTauriBackend } from "@/hooks/useTauriBackend";
import TabBar from "@/components/TabBar";
import Toolbar from "@/components/Toolbar";
import MenuBar, { type MenuGroup } from "@/components/MenuBar";
import EditorPane from "@/components/EditorPane";
import PreviewPane from "@/components/PreviewPane";
import SplitPane from "@/components/SplitPane";
import AIPanel, { type AIPanelTab } from "@/components/AIPanel";
import CitationPanel from "@/components/CitationPanel";
import SlashCommandMenu from "@/components/SlashCommandMenu";
import StatusBar from "@/components/StatusBar";
import { AI } from "@/lib/api";
import {
  resolveShortcutDefinitions,
  shortcutMatchesEvent,
  isEditableTarget,
  type ActionId,
} from "@/lib/keyboardShortcuts";

export default function HomePage() {
  const editor = useEditor();
  const [showPreview] = useState(true);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const [showCitationPanel, setShowCitationPanel] = useState(false);
  const [aiPanelInitialTab, setAiPanelInitialTab] = useState<AIPanelTab | undefined>(undefined);
  const [split, setSplit] = useState(50);
  const [monacoReady, setMonacoReady] = useState(false);
  const [selectedText, setSelectedText] = useState("");
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus } = useTauriBackend(editor);
  const fileIO = useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef });
  const { handleOpenFile, handleExport } = fileIO;

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

  const insertCitation = useCallback(
    (citationKey: string) => {
      replaceSelection("insert-citation", () => ({
        text: `[@${citationKey}]`,
        cursorOffset: `[@${citationKey}]`.length,
      }));
    },
    [replaceSelection]
  );

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
      "view.fullEditor": () => setSplit(100),
      "view.balancedSplit": () => setSplit(50),
      "view.fullPreview": () => setSplit(0),
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
          "separator",
          { id: "view.fullEditor", label: "Full Width Editor", onSelect: actions["view.fullEditor"] },
          { id: "view.balancedSplit", label: "Balanced Split View", onSelect: actions["view.balancedSplit"] },
          { id: "view.fullPreview", label: "Full Width Preview", onSelect: actions["view.fullPreview"] },
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
      // Tauri's packaged WebView and Monaco can handle bubbling key events
      // before they reach this listener. Capture the event so app shortcuts
      // remain available regardless of which editor element has focus.
      // Never intercept keys while an IME composition is in progress.
      if (event.isComposing) return;
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

    window.addEventListener("keydown", onKeyDown, true);
    return () => window.removeEventListener("keydown", onKeyDown, true);
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

  const getSelectedText = useCallback(() => {
    const mono = monacoRef.current;
    if (!mono) return "";
    const sel = mono.getSelection();
    if (!sel) return "";
    return mono.getModel()?.getValueInRange(sel) ?? "";
  }, []);

  const syncSelectedText = useCallback(() => {
    setSelectedText(getSelectedText());
  }, [getSelectedText]);

  // ── Slash commands ──────────────────────────────────────────────────────────
  const slash = useSlashCommands();

  const executeSlashCommand = useCallback(
    async (command: SlashCommand) => {
      const mono = monacoRef.current;
      const model = mono?.getModel();
      const trigger = slash.triggerPosition;
      const position = mono?.getPosition();
      if (mono && model && trigger && position) {
        mono.executeEdits("slash-command", [
          {
            range: {
              startLineNumber: trigger.lineNumber,
              startColumn: trigger.column - 1,
              endLineNumber: position.lineNumber,
              endColumn: position.column,
            },
            text: "",
          },
        ]);
        mono.focus();
      }
      slash.close();

      // Read the live buffer post-edit — editor.activeTab.content is React state
      // and has not yet caught up with the executeEdits call above.
      const documentText = model?.getValue() ?? editor.activeTab.content;

      if (command.kind === "insert-table") {
        insertTable();
        return;
      }
      if (command.kind === "open-translate-tab") {
        setAiPanelInitialTab("translate");
        setShowAIPanel(true);
        return;
      }
      if (!command.prompt) {
        alert(`AI command "${command.label}" is not available (automation templates failed to load).`);
        return;
      }
      try {
        const result = await AI.chat({
          message: command.prompt,
          document_text: documentText,
          selected_text: getSelectedText(),
          chat_history: [],
        });
        if (result.proposed_action.type !== "none") {
          handleAIApplyAction(result.proposed_action.type, result.proposed_action.content);
        } else if (result.assistant_message) {
          alert(result.assistant_message);
        }
      } catch (err) {
        alert(`AI command failed: ${err instanceof Error ? err.message : String(err)}`);
      }
    },
    [slash, insertTable, editor, handleAIApplyAction, getSelectedText]
  );

  const slashRef = useRef({
    isOpen: slash.isOpen,
    triggerPosition: slash.triggerPosition,
    moveSelection: slash.moveSelection,
    close: slash.close,
    openAt: slash.openAt,
    getSelectedCommand: slash.getSelectedCommand,
    execute: executeSlashCommand,
  });
  useEffect(() => {
    slashRef.current = {
      isOpen: slash.isOpen,
      triggerPosition: slash.triggerPosition,
      moveSelection: slash.moveSelection,
      close: slash.close,
      openAt: slash.openAt,
      getSelectedCommand: slash.getSelectedCommand,
      execute: executeSlashCommand,
    };
  });

  useEffect(() => {
    const mono = monacoRef.current;
    if (!mono || !monacoReady) return;

    const handleSync = () => {
      syncSelectedText();
      const model = mono.getModel();
      const position = mono.getPosition();
      if (!model || !position) return;
      const s = slashRef.current;

      if (!s.isOpen) {
        if (isSlashTriggerPosition(model, position)) {
          s.openAt(position);
        }
        return;
      }

      const trigger = s.triggerPosition;
      if (!trigger || position.lineNumber !== trigger.lineNumber || position.column < trigger.column) {
        s.close();
        return;
      }
      const lineContent = model.getLineContent(trigger.lineNumber);
      if (lineContent.charAt(trigger.column - 2) !== "/") {
        s.close();
        return;
      }
      const queryText = model.getValueInRange({
        startLineNumber: trigger.lineNumber,
        startColumn: trigger.column,
        endLineNumber: position.lineNumber,
        endColumn: position.column,
      });
      if (/\s/.test(queryText)) {
        s.close();
        return;
      }
      slash.updateQuery(queryText);
    };

    const d1 = mono.onDidChangeModelContent(handleSync);
    const d2 = mono.onDidChangeCursorPosition(handleSync);
    const d3 = mono.onDidChangeCursorSelection(syncSelectedText);
    const d4 = mono.onKeyDown((event) => {
      const s = slashRef.current;
      if (!s.isOpen) return;
      const key = event.browserEvent.key;
      if (key === "ArrowDown") {
        event.preventDefault();
        event.stopPropagation();
        s.moveSelection(1);
      } else if (key === "ArrowUp") {
        event.preventDefault();
        event.stopPropagation();
        s.moveSelection(-1);
      } else if (key === "Enter") {
        const cmd = s.getSelectedCommand();
        if (cmd) {
          event.preventDefault();
          event.stopPropagation();
          void s.execute(cmd);
        }
      } else if (key === "Escape") {
        event.preventDefault();
        event.stopPropagation();
        s.close();
      }
    });

    return () => {
      d1.dispose();
      d2.dispose();
      d3.dispose();
      d4.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [monacoReady, syncSelectedText]);

  const slashMenuPosition =
    slash.isOpen && slash.triggerPosition && monacoRef.current
      ? monacoRef.current.getScrolledVisiblePosition(slash.triggerPosition)
      : null;

  return (
    <div
      className={`flex flex-col h-screen overflow-hidden ${editor.darkMode ? "dark" : ""}`}
      style={{ background: editor.darkMode ? "#1e1e1e" : "#fff" }}
      onDragEnter={fileIO.handleDragEnter}
      onDragLeave={fileIO.handleDragLeave}
      onDragOver={fileIO.handleDragOver}
      onDrop={fileIO.handleDrop}
    >
      {/* Hidden file input for open-file */}
      <input
        ref={fileIO.fileInputRef}
        type="file"
        accept=".md,.markdown,.txt,.html,.htm,.pdf,.docx"
        className="hidden"
        onChange={fileIO.handleFileInputChange}
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
          onToggleCitationPanel={() => setShowCitationPanel((v) => !v)}
          darkMode={editor.darkMode}
          fontSize={editor.fontSize}
          onFontSizeChange={editor.setFontSize}
          showAIPanel={showAIPanel}
          showCitationPanel={showCitationPanel}
          backendStatus={showPackagedBackendStatus ? backendStatus : "ready"}
          backendMessage={showPackagedBackendStatus ? backendMessage : null}
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
          split={split}
          onSplitChange={setSplit}
          left={
            <div className="relative h-full">
              <EditorPane
                value={editor.activeTab.content}
                onChange={editor.handleContentChange}
                darkMode={editor.darkMode}
                fontSize={editor.fontSize}
                onMount={(e) => { monacoRef.current = e; setMonacoReady(true); }}
              />
              {slash.isOpen && slashMenuPosition && (
                <SlashCommandMenu
                  commands={slash.filteredCommands}
                  selectedIndex={slash.selectedIndex}
                  top={slashMenuPosition.top + slashMenuPosition.height}
                  left={slashMenuPosition.left}
                  onSelect={(cmd) => { void executeSlashCommand(cmd); }}
                  onClose={slash.close}
                />
              )}
            </div>
          }
          right={
            showPreview ? (
              <PreviewPane
                html={editor.previewHtml}
                loading={showPackagedBackendStatus && backendStatus === "starting"}
                error={showPackagedBackendStatus && backendStatus === "error" ? backendMessage : null}
              />
            ) : null
          }
        />

        {/* AI Panel */}
        {showAIPanel && (
          <AIPanel
            documentText={editor.activeTab.content}
            selectedText={selectedText}
            onApplyAction={handleAIApplyAction}
            initialTab={aiPanelInitialTab}
          />
        )}

        {/* Citation Panel */}
        {showCitationPanel && <CitationPanel onInsert={insertCitation} />}
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
