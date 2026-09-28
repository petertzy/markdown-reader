"use client";

import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { useEditor } from "@/hooks/useEditor";
import type { useFileIO } from "@/hooks/useFileIO";
import type { AIPanelTab } from "@/components/AIPanel";
import { useEditorFormatting } from "@/hooks/editor/useEditorFormatting";
import { useActions } from "@/hooks/editor/useActions";
import { useKeyboardShortcuts } from "@/hooks/editor/useKeyboardShortcuts";
import { useSlashCommands } from "@/hooks/useSlashCommands";
import { useSlashCommandWiring } from "@/hooks/editor/useSlashCommandWiring";

export type UseEditorCommandsOptions = {
  editor: ReturnType<typeof useEditor>;
  fileIO: Pick<ReturnType<typeof useFileIO>, "handleOpenFile" | "handleExport">;
  backendStatus: "starting" | "ready" | "error";
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
  monacoReady: boolean;
  setShowAIPanel: Dispatch<SetStateAction<boolean>>;
  setAiPanelInitialTab: Dispatch<SetStateAction<AIPanelTab | undefined>>;
  setSplit: Dispatch<SetStateAction<number>>;
  executeAIPrompt: (prompt: string, documentText: string) => Promise<string | null | undefined>;
  syncSelectedText: () => void;
};

/**
 * Encapsulates the Markdown formatting commands, action definitions, keyboard shortcuts,
 * and slash command wiring into a cohesive module, removing this responsibility from the homepage.
 */
export function useEditorCommands({
  editor,
  fileIO,
  backendStatus,
  monacoRef,
  monacoReady,
  setShowAIPanel,
  setAiPanelInitialTab,
  setSplit,
  executeAIPrompt,
  syncSelectedText,
}: UseEditorCommandsOptions) {
  // 1. Markdown formatting logic (bold, italic, headings, tables, citations)
  const formatting = useEditorFormatting(monacoRef);

  // 2. Action definitions and shortcut mapping
  const { actions, menuGroups, shortcuts, handleSaveFile, handleOpenBrowserPreview } = useActions({
    editor,
    fileIO,
    formatting,
    backendStatus,
    monacoRef,
    setShowAIPanel,
    setSplit,
  });

  // 3. Register keyboard shortcuts
  useKeyboardShortcuts(shortcuts, actions);

  // 4. Slash commands state and execution wiring
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

  return {
    formatting,
    actions,
    menuGroups,
    shortcuts,
    handleSaveFile,
    handleOpenBrowserPreview,
    slash,
    executeSlashCommand,
    slashMenuPosition,
  };
}

export type EditorCommandsController = ReturnType<typeof useEditorCommands>;
