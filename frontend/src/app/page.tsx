"use client";

import { useState, useRef, useCallback, type SetStateAction } from "react";
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
import FocusModePane from "@/components/FocusModePane";
import AIPanel, { type AIPanelTab } from "@/components/AIPanel";
import CitationPanel from "@/components/CitationPanel";
import SlashCommandMenu from "@/components/SlashCommandMenu";
import StatusBar from "@/components/StatusBar";
import { PANELS, type PanelId } from "@/types/panels";

export default function HomePage() {
  const editor = useEditor();
  const [focusMode, setFocusMode] = useState(false);
  const [focusRevision, setFocusRevision] = useState(0);
  const [showPreview] = useState(true);
  const [activePanel, setActivePanel] = useState<PanelId>(null);
  const [aiPanelInitialTab, setAiPanelInitialTab] = useState<AIPanelTab | undefined>();
  const [split, setSplit] = useState(50);
  const [monacoReady, setMonacoReady] = useState(false);
  const monacoRef = useRef<MonacoEditor.IStandaloneCodeEditor | null>(null);
  const { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus } = useTauriBackend(editor);
  const fileIO = useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef });
  const formatting = useEditorFormatting(monacoRef);
  const { selectedText, syncSelectedText, applyAction: handleAIApplyAction, executePrompt: executeAIPrompt } = useAIActions({
    documentText: editor.activeTab.content, editorRef: monacoRef, onDocumentChange: editor.handleContentChange,
  });
  const handleToggle = (panelId: PanelId) => {
    if (activePanel === panelId) {
      setActivePanel(null);
    } else {
      setActivePanel(panelId);
    }
  };

  /**
   * Adapter function to maintain compatibility with `useActions` and `useSlashCommandWiring`.
   * Those hooks still expect a standard boolean state setter (`setShowAIPanel`), so this
   * wrapper intercepts those boolean calls and translates them into the unified `activePanel` string state.
   */
  const setShowAIPanel = (action: SetStateAction<boolean>) => {
    setActivePanel((prevPanel) => {
      const isCurrentlyAI = prevPanel === PANELS.AI;
      const shouldShowAI = typeof action === "function" ? action(isCurrentlyAI) : action;

      if (shouldShowAI) return PANELS.AI;
      if (!shouldShowAI && isCurrentlyAI) return null;
      return prevPanel;
    });
  };

  const { actions, menuGroups, shortcuts, handleSaveFile, handleOpenBrowserPreview } = useActions({
    editor, fileIO, formatting, backendStatus, monacoRef, setShowAIPanel, setSplit,
  });
  useKeyboardShortcuts(shortcuts, actions);
  const slash = useSlashCommands();
  const { executeSlashCommand, slashMenuPosition } = useSlashCommandWiring({
    monacoRef, monacoReady, slash, insertTable: formatting.insertTable, executeAIPrompt,
    documentText: editor.activeTab.content, syncSelectedText, setShowAIPanel, setAiPanelInitialTab,
  });
  const handleTabSelect = useCallback((id: string) => {
    editor.setActiveTabId(id);
    const tab = editor.tabs.find((item) => item.id === id);
    if (tab) editor.refreshPreview(tab.content, tab.filePath ?? undefined);
  }, [editor]);

  return (
    <div className={`flex flex-col h-screen overflow-hidden ${editor.darkMode ? "dark" : ""}`}
      style={{ background: editor.darkMode ? "#1e1e1e" : "#fff" }}
      onDragEnter={fileIO.handleDragEnter} onDragLeave={fileIO.handleDragLeave}
      onDragOver={fileIO.handleDragOver} onDrop={fileIO.handleDrop}>
      <input ref={fileIO.fileInputRef} type="file" accept={fileIO.fileInputAccept} className="hidden" onChange={fileIO.handleFileInputChange} />
      <MenuBar groups={menuGroups} shortcuts={shortcuts} />
      <Toolbar onOpenFile={() => { void fileIO.handleOpenFile(); }} onSaveFile={() => { void handleSaveFile(); }}
        onExport={fileIO.handleExport} onOpenBrowserPreview={() => { void handleOpenBrowserPreview(); }}
        onToggleDark={() => editor.setDarkMode((dark) => !dark)} activePanel={activePanel} onTogglePanel={handleToggle}
        onToggleFocusMode={() => { setFocusMode((enabled) => !enabled); setMonacoReady(false); monacoRef.current = null; setFocusRevision((revision) => revision + 1); }}
        darkMode={editor.darkMode} fontSize={editor.fontSize} onFontSizeChange={editor.setFontSize}
        showFocusPanel={focusMode}
        backendStatus={showPackagedBackendStatus ? backendStatus : "ready"} backendMessage={showPackagedBackendStatus ? backendMessage : null} />
      <TabBar tabs={editor.tabs} activeTabId={editor.activeTabId} onSelect={handleTabSelect} onClose={editor.closeTab} onNew={editor.newTab} />
      <div className="flex flex-1 overflow-hidden">
        {focusMode ? <FocusModePane key={`${editor.activeTabId}-${focusRevision}`} value={editor.activeTab.content}
          onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
          slashCommands={slash.filteredCommands} onSelect={(command) => { void executeSlashCommand(command); }} /> :
          <SplitPane split={split} onSplitChange={setSplit}
            left={<div className="relative h-full"><EditorPane path={editor.activeTab.id} value={editor.activeTab.content}
              onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
              onMount={(instance) => { monacoRef.current = instance; setMonacoReady(true); }} />
              {slash.isOpen && slashMenuPosition && <SlashCommandMenu commands={slash.filteredCommands} selectedIndex={slash.selectedIndex}
                top={slashMenuPosition.top + slashMenuPosition.height} left={slashMenuPosition.left}
                onSelect={(command) => { void executeSlashCommand(command); }} onClose={slash.close} />}</div>}
            right={showPreview ? <PreviewPane html={editor.previewHtml} loading={showPackagedBackendStatus && backendStatus === "starting"}
              error={showPackagedBackendStatus && backendStatus === "error" ? backendMessage : null} /> : null} />}
        {activePanel === PANELS.AI && <AIPanel documentText={editor.activeTab.content} selectedText={selectedText} onApplyAction={handleAIApplyAction} initialTab={aiPanelInitialTab} />}
        {activePanel === PANELS.CITATION && <CitationPanel onInsert={formatting.insertCitation} />}
      </div>
      <StatusBar stats={editor.wordCount} filePath={editor.activeTab.filePath} dirty={editor.activeTab.dirty} />
    </div>
  );
}
