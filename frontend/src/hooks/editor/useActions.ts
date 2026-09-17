"use client";

import { useCallback, useMemo } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { useEditor } from "@/hooks/useEditor";
import type { useFileIO } from "@/hooks/useFileIO";
import type { EditorFormattingController } from "@/hooks/editor/useEditorFormatting";
import type { MenuGroup } from "@/components/MenuBar";
import { Markdown } from "@/lib/api";
import {
  resolveShortcutDefinitions,
  type ActionId,
  type ShortcutDefinition,
} from "@/lib/keyboardShortcuts";

type EditorController = ReturnType<typeof useEditor>;
type FileIOController = ReturnType<typeof useFileIO>;

export type UseActionsOptions = {
  editor: EditorController;
  fileIO: Pick<FileIOController, "handleOpenFile" | "handleExport">;
  formatting: EditorFormattingController;
  backendStatus: "starting" | "ready" | "error";
  monacoRef: MutableRefObject<MonacoEditor.IStandaloneCodeEditor | null>;
  setShowAIPanel: Dispatch<SetStateAction<boolean>>;
  setSplit: Dispatch<SetStateAction<number>>;
};

export function useActions({
  editor,
  fileIO,
  formatting,
  backendStatus,
  monacoRef,
  setShowAIPanel,
  setSplit,
}: UseActionsOptions) {
  const { handleOpenFile, handleExport } = fileIO;
  const {
    runMonacoAction,
    wrapSelection,
    applyHeading,
    insertTable,
  } = formatting;

  const handleSaveFile = useCallback(async () => {
    try {
      await editor.saveFile();
    } catch (err) {
      alert(`Save failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [editor]);

  const handleOpenBrowserPreview = useCallback(async () => {
    if (backendStatus !== "ready") return;
    try {
      await Markdown.openPreviewInBrowser({
        content: monacoRef.current?.getValue() ?? editor.activeTab.content,
        base_dir: editor.activeTab.filePath?.replace(/[^/\\]+$/, ""),
        dark_mode: editor.darkMode,
        font_size: editor.fontSize,
      });
    } catch (err) {
      alert(`Open browser preview failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [backendStatus, editor.activeTab.content, editor.activeTab.filePath, editor.darkMode, editor.fontSize, monacoRef]);

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
      "view.openBrowserPreview": () => { void handleOpenBrowserPreview(); },
      "view.fullEditor": () => setSplit(100),
      "view.balancedSplit": () => setSplit(50),
      "view.fullPreview": () => setSplit(0),
    }),
    [
      applyHeading,
      editor,
      handleOpenFile,
      handleExport,
      handleOpenBrowserPreview,
      handleSaveFile,
      insertTable,
      runMonacoAction,
      setShowAIPanel,
      setSplit,
      wrapSelection,
    ]
  );

  const shortcuts: ShortcutDefinition[] = useMemo(() => resolveShortcutDefinitions(), []);
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
          { id: "view.openBrowserPreview", label: "Open Preview in Browser", onSelect: actions["view.openBrowserPreview"], disabled: backendDisabled },
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

  return {
    actions,
    menuGroups,
    shortcuts,
    handleSaveFile,
    handleOpenBrowserPreview,
  };
}
