"use client";

import { useState, useCallback, useRef, type SetStateAction } from "react";
import { useEditor } from "@/hooks/useEditor";
import { useAIActions } from "@/hooks/useAIActions";
import { useProjectWorkspace } from "@/hooks/useProjectWorkspace";
import { useProjectWork } from "@/hooks/useProjectWork";
import { useFileIO } from "@/hooks/useFileIO";
import { usePanels } from "@/hooks/usePanels";
import { useTauriBackend } from "@/hooks/useTauriBackend";
import { useEditorCommands } from "@/hooks/editor/useEditorCommands";
import { useEditorWorkspace } from "@/hooks/editor/useEditorWorkspace";
import TabBar from "@/components/TabBar";
import Toolbar from "@/components/Toolbar";
import MenuBar from "@/components/MenuBar";
import EditorWorkspace from "@/components/EditorWorkspace";
import PreviewPane from "@/components/PreviewPane";
import SplitPane from "@/components/SplitPane";
import FocusModePane, { type FocusEditorHandle } from "@/components/FocusModePane";
import AIPanel, { type AIPanelTab } from "@/components/AIPanel";
import CitationPanel from "@/components/CitationPanel";
import PublicationPanel from "@/components/PublicationPanel";
import ProjectExplorer from "@/components/ProjectExplorer";
import DocumentStats from "@/components/DocumentStats";
import StatusBar from "@/components/StatusBar";
import { PANELS } from "@/types/panels";

export default function HomePage() {
  const editor = useEditor();
  const project = useProjectWorkspace();
  const projectWork = useProjectWork(editor, project.projectRoot);
  const editorWorkspace = useEditorWorkspace();
  const {
    monacoRef,
    monacoReady,
    revision,
    markReady,
    reset: resetEditor,
  } = editorWorkspace;
  const [focusMode, setFocusMode] = useState(false);
  const { activePanel, togglePanel, hidePanel, setShowAIPanel } = usePanels();
  // Focus Mode undo/redo handle (issue #341) — published by FocusModePane.
  const focusEditorRef = useRef<FocusEditorHandle | null>(null);
  const [aiPanelInitialTab, setAiPanelInitialTab] = useState<AIPanelTab | undefined>();
  const [split, setSplit] = useState(50);
  const [projectRefreshToken, setProjectRefreshToken] = useState(0);
  const { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus } = useTauriBackend(editor);
  const showPreview = true;
  const projectRoot: string | null = null; // placeholder hasta conectar openProject
  const fileIO = useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef });
  const { selectedText, syncSelectedText, applyAction: handleAIApplyAction, executePrompt: executeAIPrompt, executeWork, isWorking } = useAIActions({
    documentId: editor.activeTab.id, documentText: editor.activeTab.content, editorRef: monacoRef, onDocumentChange: editor.handleContentChange,
  });
  const selectPanel = useCallback((panel: NonNullable<typeof PANELS[keyof typeof PANELS]>) => {
    togglePanel(panel);
    setSplit(panel === PANELS.PREVIEW ? 50 : 60);
  }, [togglePanel]);
  const openProject = useCallback(async () => {
    const root = await project.openProject();
    if (!root) return;
    hidePanel();
    setSplit(100);
    await editor.openProjectAsMarkdown(root);
  }, [editor, hidePanel, project]);
  const setShowAIPanelWithLayout = useCallback((action: SetStateAction<boolean>) => {
    const aiVisible = activePanel === PANELS.AI;
    const showAI = typeof action === "function" ? action(aiVisible) : action;
    setShowAIPanel(action);
    setSplit(showAI ? 60 : 50);
  }, [activePanel, setShowAIPanel]);

  const {
    formatting,
    menuGroups,
    shortcuts,
    handleSaveFile,
    handleOpenBrowserPreview,
    slash,
    executeSlashCommand,
    slashMenuPosition,
  } = useEditorCommands({
    editor,
    fileIO,
    backendStatus,
    monacoRef,
    monacoReady,
    setShowAIPanel: setShowAIPanelWithLayout,
    focusEditorRef,
    setAiPanelInitialTab,
    setSplit,
    onOpenProject: () => { void openProject(); },
    onFileSaved: () => setProjectRefreshToken((token) => token + 1),
    onShowPreview: () => selectPanel(PANELS.PREVIEW),
    executeAIPrompt,
    syncSelectedText,
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
        onOpenProject={() => { void openProject(); }}
        onExport={fileIO.handleExport} onOpenBrowserPreview={() => { void handleOpenBrowserPreview(); }}
        onToggleDark={() => editor.setDarkMode((dark) => !dark)} activePanel={activePanel} onTogglePanel={togglePanel}
        onToggleFocusMode={() => { setFocusMode((enabled) => !enabled); resetEditor(); }}
        darkMode={editor.darkMode} fontSize={editor.fontSize} onFontSizeChange={editor.setFontSize}
        showFocusPanel={focusMode}
        backendStatus={showPackagedBackendStatus ? backendStatus : "ready"} backendMessage={showPackagedBackendStatus ? backendMessage : null}
        lastExportedPath={fileIO.lastExportedPath} onShowInFinder={fileIO.showInFinder} />
      <TabBar tabs={editor.tabs} activeTabId={editor.activeTabId} onSelect={handleTabSelect} onClose={editor.closeTab} onNew={editor.newTab} />
      <div className="flex flex-1 overflow-hidden">
        {focusMode ? <FocusModePane key={`${editor.activeTabId}-${revision}`} value={editor.activeTab.content}
          onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
          slashCommands={slash.filteredCommands} onSelect={(command) => { void executeSlashCommand(command); }}
          editorRef={focusEditorRef} /> :
          <SplitPane split={split} onSplitChange={setSplit}
            left={<EditorWorkspace tabId={editor.activeTab.id} value={editor.activeTab.content}
              onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
              revision={revision} monacoRef={monacoRef} onReady={markReady}
              slash={{ isOpen: slash.isOpen, filteredCommands: slash.filteredCommands, selectedIndex: slash.selectedIndex,
                position: slashMenuPosition,
                onSelect: (command) => { void executeSlashCommand(command); }, onClose: slash.close }} />}
            right={showPreview ? <PreviewPane html={editor.previewHtml} loading={showPackagedBackendStatus && backendStatus === "starting"}
              error={showPackagedBackendStatus && backendStatus === "error" ? backendMessage : null} /> : null} />}
        {activePanel === PANELS.AI && (
          <AIPanel
            documentText={editor.activeTab.content}
            selectedText={selectedText}
            onApplyAction={handleAIApplyAction}
            initialTab={aiPanelInitialTab}
            executeWork={executeWork}
            isWorking={isWorking}
            documentId={editor.activeTab.id}      /* <-- nuevo */
            projectRoot={projectRoot}             /* <-- nuevo */
            projectWork={projectWork}            
          />
        )}
        {activePanel === PANELS.CITATION && <CitationPanel onInsert={formatting.insertCitation} />}
        {activePanel === PANELS.PUBLICATION && (
          <PublicationPanel tabs={editor.tabs} onClose={() => togglePanel(PANELS.PUBLICATION)} />
        )}
        {activePanel === PANELS.EXPLORER && (
          <ProjectExplorer
            rootPath={projectRoot ?? ""}   /* ✅ string */
            refreshToken={projectRefreshToken}
            onClose={() => togglePanel(PANELS.EXPLORER)}
          />
        )}
      </div>
      <DocumentStats content={editor.activeTab.content} className="px-4 py-1 border-t" />
      <StatusBar stats={editor.wordCount} filePath={editor.activeTab.filePath} dirty={editor.activeTab.dirty} />
    </div>
  );
}

