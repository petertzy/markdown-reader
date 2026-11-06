"use client";

/**
 * Toolbar.tsx
 * ===========
 * Top action bar: file open/save, export, view toggles, settings.
 */

import { useEffect, useState } from "react";
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";

import { PANELS, type PanelId } from "@/types/panels";
import { DEFAULT_SHORTCUTS, formatShortcut } from "@/lib/keyboardShortcuts";

const MIN_FONT_SIZE = 8;
const MAX_FONT_SIZE = 72;

type Props = {
  onOpenFile: () => void;
  onOpenProject: () => void;
  onSaveFile: () => void;
  onExport: (format: "html" | "pdf" | "docx") => void;
  onOpenBrowserPreview: () => void;
  onToggleDark: () => void;
  activePanel: PanelId;
  onTogglePanel: (id: NonNullable<PanelId>) => void;
  onToggleFocusMode: () => void;
  darkMode: boolean;
  fontSize: number;
  onFontSizeChange: (size: number) => void;
  showFocusPanel: boolean;
  backendStatus?: "starting" | "ready" | "error";
  backendMessage?: string | null;
  lastExportedPath?: string | null;
  onShowInFinder?: () => void;
};

export default function Toolbar({
  onOpenFile,
  onOpenProject,
  onSaveFile,
  onExport,
  onOpenBrowserPreview,
  onToggleDark,
  onTogglePanel,
  onToggleFocusMode,
  activePanel,
  darkMode,
  fontSize,
  onFontSizeChange,
  onShowInFinder,
  showFocusPanel,
  backendStatus = "ready",
  backendMessage = null,
  lastExportedPath = null,
}: Props) {
  const backendBusy = backendStatus === "starting";
  const backendFailed = backendStatus === "error";
  const backendDisabled = backendBusy || backendFailed;

  const [fontSizeInput, setFontSizeInput] = useState(String(fontSize));

  useEffect(() => {
    setFontSizeInput(String(fontSize));
  }, [fontSize]);

  const isValidFontSize = (value: number) =>
    Number.isInteger(value) && value >= MIN_FONT_SIZE && value <= MAX_FONT_SIZE;

  const commitFontSize = () => {
    const value = Number(fontSizeInput);

    if (isValidFontSize(value)) {
      onFontSizeChange(value);
      setFontSizeInput(String(value));
    } else {
      setFontSizeInput(String(fontSize));
    }
  };

  const keepEditorFocused = (event: ReactMouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };
  const keepEditorFocusedOnPointerDown = (event: ReactPointerEvent<HTMLButtonElement>) => {
    event.preventDefault();
  };

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-1 px-2 py-1 bg-white dark:bg-[#252526] border-b border-gray-200 dark:border-gray-700 shrink-0 text-sm">
      {/* File ops */}
      <IconButton icon="📂" label="Open file" shortcutId="file.open" onClick={onOpenFile} disabled={backendDisabled} />
      <IconButton icon="🗂️" label="Open project folder" shortcutId="file.openFolder" onClick={onOpenProject} disabled={backendDisabled} />
      <IconButton icon="💾" label="Save" shortcutId="file.save" onClick={onSaveFile} disabled={backendDisabled} />
      {lastExportedPath && (
        <button onClick={onShowInFinder} className={btnCls} title="Show the last export in Finder">
          📁 Show in Finder
        </button>
      )}

      <Divider />

      {/* Export: the format names are the information, so they stay as text. */}
      <span className="text-gray-400 text-xs">Export:</span>
      {(["html", "pdf", "docx"] as const).map((fmt) => (
        <button key={fmt} onPointerDown={keepEditorFocusedOnPointerDown} onMouseDown={keepEditorFocused} onClick={() => onExport(fmt)} className={buttonClass(backendDisabled)} disabled={backendDisabled} title={withShortcut(`Export to ${fmt.toUpperCase()}`, `file.export${EXPORT_ACTION_SUFFIX[fmt]}`)}>
          {fmt.toUpperCase()}
        </button>
      ))}
      <IconButton icon="🌐" label="Open rendered preview in browser" shortcutId="view.openBrowserPreview" onClick={onOpenBrowserPreview} disabled={backendDisabled} />

      <Divider />

      {/* Font size */}
      <span className="text-gray-500 dark:text-gray-400 text-xs">Font:</span>
      <button onPointerDown={keepEditorFocusedOnPointerDown} onMouseDown={keepEditorFocused} onClick={() => onFontSizeChange(Math.max(MIN_FONT_SIZE, fontSize - 1))} className={btnCls} title="Decrease font size" aria-label="Decrease font size">A-</button>

      <input
        type="number"
        min={MIN_FONT_SIZE}
        max={MAX_FONT_SIZE}
        step={1}
        inputMode="numeric"
        aria-label="Editor font size"
        title={`Font size (${MIN_FONT_SIZE}-${MAX_FONT_SIZE})`}
        value={fontSizeInput}
        onChange={(e) => {
          const input = e.target.value;
          setFontSizeInput(input);

          const value = Number(input);
          if (isValidFontSize(value)) onFontSizeChange(value);
        }}
        onFocus={(e) => e.target.select()}
        onBlur={commitFontSize}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            commitFontSize();
            e.currentTarget.blur();
          }

          if (e.key === "Escape") {
            setFontSizeInput(String(fontSize));
            e.currentTarget.blur();
          }
        }}
        className="w-12 text-center text-xs rounded border border-gray-300 dark:border-gray-600 bg-white dark:bg-[#252526] text-gray-700 dark:text-gray-300"
      />

      <button onPointerDown={keepEditorFocusedOnPointerDown} onMouseDown={keepEditorFocused} onClick={() => onFontSizeChange(Math.min(MAX_FONT_SIZE, fontSize + 1))} className={btnCls} title="Increase font size" aria-label="Increase font size">A+</button>

      <div className="flex-1" />

      {backendBusy && (
        <span className="text-xs text-amber-600 dark:text-amber-300 whitespace-nowrap">
          Starting backend...
        </span>
      )}
      {backendFailed && (
        <span className="text-xs text-red-600 dark:text-red-300 truncate max-w-[220px]" title={backendMessage ?? undefined}>
          Backend unavailable
        </span>
      )}

      {/* Toggles */}
      <IconButton icon="🧠" label="Focus Mode" shortcutId="view.toggleFocusMode" onClick={onToggleFocusMode} pressed={showFocusPanel} />
      <IconButton icon="👁" label="Preview" shortcutId="view.showPreview" onClick={() => onTogglePanel(PANELS.PREVIEW)} pressed={activePanel === PANELS.PREVIEW} />
      <IconButton icon="🤖" label="AI Assistant" shortcutId="view.toggleAIPanel" onClick={() => onTogglePanel(PANELS.AI)} pressed={activePanel === PANELS.AI} />
      <IconButton icon="📚" label="Citations" onClick={() => onTogglePanel(PANELS.CITATION)} pressed={activePanel === PANELS.CITATION} />
      <IconButton icon="📝" label="Publication" onClick={() => onTogglePanel(PANELS.PUBLICATION)} pressed={activePanel === PANELS.PUBLICATION} />
      <IconButton icon={darkMode ? "☀️" : "🌙"} label={darkMode ? "Switch to light mode" : "Switch to dark mode"} shortcutId="view.toggleDarkMode" onClick={onToggleDark} />
    </div>
  );
}

const EXPORT_ACTION_SUFFIX = { html: "Html", pdf: "Pdf", docx: "Docx" } as const;

/** "Save (Cmd+S)": the label plus the shortcut bound to `shortcutId`, if any. */
function withShortcut(label: string, shortcutId?: string) {
  const binding = DEFAULT_SHORTCUTS.find((shortcut) => shortcut.id === shortcutId)?.bindings[0];
  return binding ? `${label} (${formatShortcut(binding)})` : label;
}

type IconButtonProps = {
  icon: string;
  /** Tooltip and accessible name; the icon alone is shown. */
  label: string;
  shortcutId?: string;
  onClick: () => void;
  disabled?: boolean;
  /** Set for toggles, so their on/off state is exposed and highlighted. */
  pressed?: boolean;
};

function IconButton({ icon, label, shortcutId, onClick, disabled = false, pressed }: IconButtonProps) {
  return (
    <button
      // Keep focus (and the selection) in the editor while clicking.
      onPointerDown={(event) => event.preventDefault()}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onClick}
      disabled={disabled}
      title={withShortcut(label, shortcutId)}
      aria-label={label}
      aria-pressed={pressed}
      className={`${buttonClass(disabled)} min-w-8 text-base leading-6 ${pressed ? activeCls : ""}`}
    >
      <span aria-hidden="true">{icon}</span>
    </button>
  );
}

function Divider() {
  return <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1" />;
}

const activeCls = "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300";

const btnCls =
  "px-2 py-0.5 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors";

function buttonClass(disabled: boolean) {
  return disabled
    ? `${btnCls} opacity-40 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent`
    : btnCls;
}
