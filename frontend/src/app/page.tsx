"use client";

/**
 * app/page.tsx
 * ============
 * Main editor page: orchestrates editor state, shortcuts,
 * slash commands, and panels into the core layout.
 */

import { useState, useRef, useCallback } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import { useEditor } from "@/hooks/useEditor";
import { useAIActions } from "@/hooks/useAIActions";
import { useSlashCommands } from "@/hooks/useSlashCommands";
import { useFileIO } from "@/hooks/useFileIO";
import { useTauriBackend } from "@/hooks/useTauriBackend";
import { useEditorFormatting } from "@/hooks/editor/useEditorFormatting";
import { useActions } from "@/hooks/editor/useActions";
import { useKeyboardShortcuts } from "@/hooks/editor/useKeyboardShortcuts";
import { useSlashCommandWiring } from "@/hooks/editor/useSlashCommandWiring";
import TabBar from "@/components/TabBar";
import Toolbar from "@/components/Toolbar";
import MenuBar from "@/components/MenuBar";
import EditorPane from "@/components/EditorPane";
import PreviewPane from "@/components/PreviewPane";
import SplitPane from "@/components/SplitPane";
import AIPanel, { type AIPanelTab } from "@/components/AIPanel";
import CitationPanel from "@/components/CitationPanel";
import SlashCommandMenu from "@/components/SlashCommandMenu";
import StatusBar from "@/components/StatusBar";

export default function HomePage() {
  const editor = useEditor();
  const [showPreview] = useState(true);
  const [showAIPanel, setShowAIPanel] = useState(false);
  const [showCitationPanel, setShowCitationPanel] = useState(false);
  const [aiPanelInitialTab, setAiPanelInitialTab] = useState<AIPanelTab | undefined>(undefined);
  const [split, setSplit] = useState(50);
  const [monacoReady, setMonacoReady] = useState(false);
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);

  const { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus } =
    useTauriBackend(editor);
  const fileIO = useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef });
  const formatting = useEditorFormatting(monacoRef);

  const {
    selectedText,
    syncSelectedText,
    applyAction: handleAIApplyAction,
    executePrompt: executeAIPrompt,
  } = useAIActions({
    documentText: editor.activeTab.content,
    editorRef: monacoRef,
    onDocumentChange: editor.handleContentChange,
  });

  const { actions, menuGroups, shortcuts, handleSaveFile, handleOpenBrowserPreview } = useActions({
    editor,
    fileIO,
    formatting,
    backendStatus,
    monacoRef,
    setShowAIPanel,
    setSplit,
  });

  useKeyboardShortcuts(shortcuts, actions);

  const slash = useSlashCommands();
  const { executeSlashCommand, slashMenuPosition } = useSlashCommandWiring({
    monacoRef,
    monacoReady,
    slash,
    insertTable: formatting.insertTable,
    executeAIPrompt,
    documentText: editor.activeTab.content,
    syncSelectedText,
    setShowAIPanel,
    setAiPanelInitialTab,
  });

  const handleTabSelect = useCallback(
    (id: string) => {
      editor.setActiveTabId(id);
      const tab = editor.tabs.find((t) => t.id === id);
      if (tab) editor.refreshPreview(tab.content, tab.filePath ?? undefined);
    },
    [editor]
  );

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
        accept={fileIO.fileInputAccept}
        className="hidden"
        onChange={fileIO.handleFileInputChange}
      />

      {/* Menu & Toolbar */}
      <MenuBar groups={menuGroups} shortcuts={shortcuts} />
      <div className="relative">
        <Toolbar
          onOpenFile={() => { void fileIO.handleOpenFile(); }}
          onSaveFile={() => { void handleSaveFile(); }}
          onExport={fileIO.handleExport}
          onOpenBrowserPreview={() => { void handleOpenBrowserPreview(); }}
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
      </div>

      {/* Tab bar */}
      <TabBar
        tabs={editor.tabs}
        activeTabId={editor.activeTabId}
        onSelect={handleTabSelect}
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
                path={editor.activeTab.id}
                value={editor.activeTab.content}
                onChange={editor.handleContentChange}
                darkMode={editor.darkMode}
                fontSize={editor.fontSize}
                onMount={(e) => {
                  monacoRef.current = e;
                  setMonacoReady(true);
                }}
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
        {showCitationPanel && <CitationPanel onInsert={formatting.insertCitation} />}
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
