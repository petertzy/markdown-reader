"use client";

import { useCallback, useMemo } from "react";
import type { Dispatch, MutableRefObject, SetStateAction } from "react";
import type { editor as MonacoEditor } from "monaco-editor";
import type { useEditor } from "@/hooks/useEditor";
import type { useFileIO } from "@/hooks/useFileIO";
import type { EditorFormattingController } from "@/hooks/editor/useEditorFormatting";
import type { MenuGroup } from "@/components/MenuBar";
import { MIN_FONT_SIZE, MAX_FONT_SIZE } from "@/components/Toolbar";
import type { FocusEditorHandle } from "@/components/FocusModePane";
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
  /**
   * Handle published by FocusModePane while Focus Mode is mounted (issue #341).
   * While non-null, `edit.undo`/`edit.redo` drive the Milkdown history instead
   * of the Monaco instance, which is null in Focus Mode.
   */
  focusEditorRef?: MutableRefObject<FocusEditorHandle | null>;
  setShowAIPanel: Dispatch<SetStateAction<boolean>>;
  setSplit: Dispatch<SetStateAction<number>>;
  onOpenProject: () => void;
  onFileSaved: () => void;
  onShowPreview: () => void;
  /** Whether clicking in the editor snaps the preview to that spot. */
  snapOnClick?: boolean;
  onToggleSnapOnClick?: () => void;
  onToggleFocusMode: () => void;
  /** Activate a tab and refresh the preview for it. */
  onSelectTab: (id: string) => void;
};

export function useActions({
  editor,
  fileIO,
  formatting,
  backendStatus,
  monacoRef,
  focusEditorRef,
  setShowAIPanel,
  setSplit,
  onOpenProject,
  onFileSaved,
  onShowPreview,
  snapOnClick = true,
  onToggleSnapOnClick,
  onToggleFocusMode,
  onSelectTab,
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
      onFileSaved();
    } catch (err) {
      alert(`Save failed: ${err instanceof Error ? err.message : String(err)}`);
    }
  }, [editor, onFileSaved]);

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

  const selectAdjacentTab = useCallback((step: 1 | -1) => {
    const { tabs, activeTabId } = editor;
    if (tabs.length < 2) return;
    const index = tabs.findIndex((tab) => tab.id === activeTabId);
    onSelectTab(tabs[(index + step + tabs.length) % tabs.length].id);
  }, [editor, onSelectTab]);

  const actions = useMemo<Record<ActionId, () => void>>(
    () => ({
      "file.new": editor.newTab,
      "file.open": () => { void handleOpenFile(); },
      "file.openFolder": onOpenProject,
      "file.save": () => { void handleSaveFile(); },
      "file.closeTab": () => editor.closeTab(editor.activeTabId),
      "file.closeAllTabs": editor.closeAllTabs,
      "file.exportHtml": () => { void handleExport("html"); },
      "file.exportPdf": () => { void handleExport("pdf"); },
      "file.exportDocx": () => { void handleExport("docx"); },
      // Focus Mode (issue #341): while FocusModePane is mounted, monacoRef is
      // null and runMonacoAction would silently no-op — route to Milkdown.
      "edit.undo": () => {
        if (focusEditorRef?.current) {
          focusEditorRef.current.undo();
          return;
        }
        runMonacoAction("undo");
      },
      "edit.redo": () => {
        if (focusEditorRef?.current) {
          focusEditorRef.current.redo();
          return;
        }
        runMonacoAction("redo");
      },
      "edit.search": () => runMonacoAction("actions.find"),
      "edit.replace": () => runMonacoAction("editor.action.startFindReplaceAction"),
      "format.bold": () => wrapSelection("bold", "**"),
      "format.italic": () => wrapSelection("italic", "*"),
      "format.underline": () => wrapSelection("underline", "<u>", "</u>"),
      "format.heading1": () => applyHeading(1),
      "format.heading2": () => applyHeading(2),
      "format.heading3": () => applyHeading(3),
      "format.normal": () => applyHeading(0),
      "format.strikethrough": () => wrapSelection("strikethrough", "~~"),
      "format.inlineCode": () => wrapSelection("inline-code", "`"),
      "format.link": () => wrapSelection("link", "[", "](url)"),
      "table.insert": insertTable,
      "view.toggleDarkMode": () => editor.setDarkMode((dark) => !dark),
      "view.toggleAIPanel": () => setShowAIPanel((visible) => !visible),
      "view.showPreview": onShowPreview,
      "view.openBrowserPreview": () => { void handleOpenBrowserPreview(); },
      "view.fullEditor": () => setSplit(100),
      "view.balancedSplit": () => setSplit(50),
      "view.fullPreview": () => setSplit(0),
      "view.toggleSnapOnClick": () => onToggleSnapOnClick?.(),
      "view.toggleFocusMode": onToggleFocusMode,
      "view.increaseFontSize": () => editor.setFontSize((size) => Math.min(MAX_FONT_SIZE, size + 1)),
      "view.decreaseFontSize": () => editor.setFontSize((size) => Math.max(MIN_FONT_SIZE, size - 1)),
      "tab.next": () => selectAdjacentTab(1),
      "tab.previous": () => selectAdjacentTab(-1),
    }),
    [
      applyHeading,
      editor,
      focusEditorRef,
      handleOpenFile,
      handleExport,
      handleOpenBrowserPreview,
      handleSaveFile,
      insertTable,
      runMonacoAction,
      setShowAIPanel,
      setSplit,
      onOpenProject,
      onShowPreview,
      onToggleSnapOnClick,
      onToggleFocusMode,
      selectAdjacentTab,
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
          { id: "file.openFolder", label: "Open Folder", onSelect: actions["file.openFolder"], disabled: backendDisabled },
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
          { id: "format.strikethrough", label: "Strikethrough", onSelect: actions["format.strikethrough"] },
          { id: "format.inlineCode", label: "Inline Code", onSelect: actions["format.inlineCode"] },
          { id: "format.link", label: "Insert Link", onSelect: actions["format.link"] },
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
          { id: "view.toggleFocusMode", label: "Toggle Focus Mode", onSelect: actions["view.toggleFocusMode"] },
          { id: "view.toggleAIPanel", label: "Show AI Agent Panel", onSelect: actions["view.toggleAIPanel"] },
          { id: "view.showPreview", label: "Toggle Preview Panel", onSelect: actions["view.showPreview"] },
          { id: "view.openBrowserPreview", label: "Open Preview in Browser", onSelect: actions["view.openBrowserPreview"], disabled: backendDisabled },
          "separator",
          { id: "view.fullEditor", label: "Full Width Editor", onSelect: actions["view.fullEditor"] },
          { id: "view.balancedSplit", label: "Balanced Split View", onSelect: actions["view.balancedSplit"] },
          { id: "view.fullPreview", label: "Full Width Preview", onSelect: actions["view.fullPreview"] },
          "separator",
          { id: "view.increaseFontSize", label: "Increase Font Size", onSelect: actions["view.increaseFontSize"] },
          { id: "view.decreaseFontSize", label: "Decrease Font Size", onSelect: actions["view.decreaseFontSize"] },
          "separator",
          { id: "tab.next", label: "Next Tab", onSelect: actions["tab.next"] },
          { id: "tab.previous", label: "Previous Tab", onSelect: actions["tab.previous"] },
          "separator",
          {
            id: "view.toggleSnapOnClick",
            label: `Snap Preview on Click: ${snapOnClick ? "On" : "Off"}`,
            onSelect: actions["view.toggleSnapOnClick"],
          },
        ],
      },
      {
        label: "Table",
        items: [{ id: "table.insert", label: "Insert Table...", onSelect: actions["table.insert"] }],
      },
      {
        label: "Shortcuts",
        // Same table as the key handler, split into categories by id prefix.
        items: shortcuts.flatMap((shortcut, index): MenuGroup["items"] => {
          const item = { id: shortcut.id, label: shortcut.label, onSelect: actions[shortcut.id] };
          const category = shortcut.id.split(".")[0];
          const startsCategory = index > 0 && shortcuts[index - 1].id.split(".")[0] !== category;
          return startsCategory ? ["separator", item] : [item];
        }),
      },
    ],
    [actions, backendDisabled, shortcuts, snapOnClick]
  );

  return {
    actions,
    menuGroups,
    shortcuts,
    handleSaveFile,
    handleOpenBrowserPreview,
  };
}
