"use client";

import { useState, useCallback, type SetStateAction } from "react";
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
import FocusModePane from "@/components/FocusModePane";
import AIPanel, { type AIPanelTab } from "@/components/AIPanel";
import CitationPanel from "@/components/CitationPanel";
import ProjectExplorer from "@/components/ProjectExplorer";
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
  const [aiPanelInitialTab, setAiPanelInitialTab] = useState<AIPanelTab | undefined>();
  const [split, setSplit] = useState(50);
  const { isDesktopRuntime, backendStatus, backendMessage, showPackagedBackendStatus } = useTauriBackend(editor);
  const fileIO = useFileIO({ editor, isDesktopRuntime, backendStatus, monacoRef });
  const { selectedText, syncSelectedText, applyAction: handleAIApplyAction, executePrompt: executeAIPrompt, executeWork, isWorking } = useAIActions({
    documentId: editor.activeTab.id, documentText: editor.activeTab.content, editorRef: monacoRef, onDocumentChange: editor.handleContentChange,
  });
  const selectPanel = useCallback((panel: NonNullable<typeof PANELS[keyof typeof PANELS]>) => {
    togglePanel(panel);
    setSplit(panel === PANELS.PREVIEW ? 50 : 70);
  }, [togglePanel]);
  const openProject = useCallback(async () => {
    if (await project.openProject()) {
      hidePanel();
      setSplit(100);
    }
  }, [hidePanel, project]);
  const setShowAIPanelWithLayout = useCallback((action: SetStateAction<boolean>) => {
    const aiVisible = activePanel === PANELS.AI;
    const showAI = typeof action === "function" ? action(aiVisible) : action;
    setShowAIPanel(action);
    setSplit(showAI ? 70 : 50);
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
    setAiPanelInitialTab,
    setSplit,
    onOpenProject: () => { void openProject(); },
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
      <Toolbar onOpenFile={() => { void fileIO.handleOpenFile(); }} onOpenProject={() => { void openProject(); }} onSaveFile={() => { void handleSaveFile(); }}
        onExport={fileIO.handleExport} onOpenBrowserPreview={() => { void handleOpenBrowserPreview(); }}
        onToggleDark={() => editor.setDarkMode((dark) => !dark)} activePanel={activePanel} onTogglePanel={selectPanel}
        onToggleFocusMode={() => { setFocusMode((enabled) => !enabled); resetEditor(); }}
        darkMode={editor.darkMode} fontSize={editor.fontSize} onFontSizeChange={editor.setFontSize}
        showFocusPanel={focusMode}
        backendStatus={showPackagedBackendStatus ? backendStatus : "ready"} backendMessage={showPackagedBackendStatus ? backendMessage : null} />
      <TabBar tabs={editor.tabs} activeTabId={editor.activeTabId} onSelect={handleTabSelect} onClose={editor.closeTab} onNew={editor.newTab} />
      <div className="flex flex-1 overflow-hidden">
        {!focusMode && <ProjectExplorer root={project.projectRoot} onOpenFile={(path) => { void editor.openFile(path); }} onOpenProject={() => { void openProject(); }} onCloseProject={project.closeProject} />}
        {focusMode ? <FocusModePane key={`${editor.activeTabId}-${revision}`} value={editor.activeTab.content}
          onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
          slashCommands={slash.filteredCommands} onSelect={(command) => { void executeSlashCommand(command); }} /> :
          <SplitPane split={split} onSplitChange={setSplit} minSize={20}
            left={<EditorWorkspace tabId={editor.activeTab.id} value={editor.activeTab.content}
              onChange={editor.handleContentChange} darkMode={editor.darkMode} fontSize={editor.fontSize}
              revision={revision} monacoRef={monacoRef} onReady={markReady}
              slash={{ isOpen: slash.isOpen, filteredCommands: slash.filteredCommands, selectedIndex: slash.selectedIndex,
                position: slashMenuPosition,
                onSelect: (command) => { void executeSlashCommand(command); }, onClose: slash.close }} />}
            right={activePanel === PANELS.PREVIEW ? <PreviewPane html={editor.previewHtml} loading={showPackagedBackendStatus && backendStatus === "starting"}
              error={showPackagedBackendStatus && backendStatus === "error" ? backendMessage : null} /> : activePanel === PANELS.AI ? <AIPanel projectRoot={project.projectRoot} projectWork={projectWork} documentText={editor.activeTab.content} selectedText={selectedText} onApplyAction={handleAIApplyAction} initialTab={aiPanelInitialTab} executeWork={executeWork} isWorking={isWorking} /> : <CitationPanel onInsert={formatting.insertCitation} />} />}
      </div>
      <StatusBar stats={editor.wordCount} filePath={editor.activeTab.filePath} dirty={editor.activeTab.dirty} />
    </div>
  );
}
