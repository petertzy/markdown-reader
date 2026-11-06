"use client";

/**
 * Toolbar.tsx
 * ===========
 * Top action bar: file open/save, export, view toggles, settings.
 *
 * Buttons whose icon says enough are icon-only, with a tooltip and an
 * accessible label. Export formats and font controls keep their text.
 */

import { useEffect, useState } from "react";
import type {
  MouseEvent as ReactMouseEvent,
  PointerEvent as ReactPointerEvent,
} from "react";

import { PANELS, type PanelId } from "@/types/panels";
import {
  DEFAULT_SHORTCUTS,
  formatShortcut,
  type ActionId,
  type ShortcutDefinition,
} from "@/lib/keyboardShortcuts";

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
  /** Current shortcuts, so tooltips show the user's own key bindings. */
  shortcuts?: ShortcutDefinition[];
};

const EXPORT_ACTIONS = {
  html: "file.exportHtml",
  pdf: "file.exportPdf",
  docx: "file.exportDocx",
} as const satisfies Record<string, ActionId>;

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
  shortcuts = DEFAULT_SHORTCUTS,
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
  const focusProps = { onPointerDown: keepEditorFocusedOnPointerDown, onMouseDown: keepEditorFocused };

  // "Save (Ctrl+S)", or just "Save" when the action has no shortcut.
  const tip = (label: string, id?: ActionId) => {
    const keys = id ? formatShortcut(shortcuts.find((s) => s.id === id)?.bindings[0]) : "";
    return keys ? `${label} (${keys})` : label;
  };

  return (
    <div className="flex items-center gap-1 px-3 py-1.5 bg-white dark:bg-[#252526] border-b border-gray-200 dark:border-gray-700 shrink-0 text-sm">
      {/* File ops */}
      <IconButton {...focusProps} icon="📂" label="Open file" title={tip("Open file", "file.open")} onClick={onOpenFile} disabled={backendDisabled} />
      <IconButton {...focusProps} icon="📁" label="Open project folder" title={tip("Open project folder", "file.openFolder")} onClick={onOpenProject} disabled={backendDisabled} />
      <IconButton {...focusProps} icon="💾" label="Save" title={tip("Save", "file.save")} onClick={onSaveFile} disabled={backendDisabled} />
      {lastExportedPath && (
        <button type="button" onClick={onShowInFinder} className={btnCls} title={`Show ${lastExportedPath}`}>
          Show in Finder
        </button>
      )}

      <Divider />

      {/* Export: format names stay as text so they can be told apart. */}
      <span className="text-gray-400 text-xs mr-0.5">Export:</span>
      {(["html", "pdf", "docx"] as const).map((fmt) => (
        <button
          key={fmt}
          type="button"
          {...focusProps}
          onClick={() => onExport(fmt)}
          className={buttonClass(backendDisabled)}
          title={tip(`Export to ${fmt.toUpperCase()}`, EXPORT_ACTIONS[fmt])}
          disabled={backendDisabled}
        >
          {fmt.toUpperCase()}
        </button>
      ))}
      <IconButton
        {...focusProps}
        icon="🌐"
        label="Open rendered preview in browser"
        title={tip("Open rendered preview in browser", "view.openBrowserPreview")}
        onClick={onOpenBrowserPreview}
        disabled={backendDisabled}
      />

      <Divider />

      {/* Font size */}
      <span className="text-gray-500 dark:text-gray-400 text-xs mr-0.5">Font:</span>
      <button
        type="button"
        {...focusProps}
        onClick={() => onFontSizeChange(Math.max(MIN_FONT_SIZE, fontSize - 1))}
        className={btnCls}
        title="Decrease font size"
        aria-label="Decrease font size"
      >
        A-
      </button>

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

      <button
        type="button"
        {...focusProps}
        onClick={() => onFontSizeChange(Math.min(MAX_FONT_SIZE, fontSize + 1))}
        className={btnCls}
        title="Increase font size"
        aria-label="Increase font size"
      >
        A+
      </button>

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
      <IconButton icon="🧠" label="Focus Mode" onClick={onToggleFocusMode} pressed={showFocusPanel} />
      <IconButton {...focusProps} icon="👁" label="Preview" onClick={() => onTogglePanel(PANELS.PREVIEW)} pressed={activePanel === PANELS.PREVIEW} />
      <IconButton
        {...focusProps}
        icon="🤖"
        label="AI Assistant"
        title={tip("AI Assistant", "view.toggleAIPanel")}
        onClick={() => onTogglePanel(PANELS.AI)}
        pressed={activePanel === PANELS.AI}
      />
      <IconButton {...focusProps} icon="📚" label="Citations" onClick={() => onTogglePanel(PANELS.CITATION)} pressed={activePanel === PANELS.CITATION} />
      <IconButton icon="📝" label="Publication" onClick={() => onTogglePanel(PANELS.PUBLICATION)} pressed={activePanel === PANELS.PUBLICATION} />
      <IconButton
        {...focusProps}
        icon={darkMode ? "☀️" : "🌙"}
        label={darkMode ? "Switch to light mode" : "Switch to dark mode"}
        title={tip(darkMode ? "Switch to light mode" : "Switch to dark mode", "view.toggleDarkMode")}
        onClick={onToggleDark}
      />
    </div>
  );
}

type IconButtonProps = {
  icon: string;
  /** Read by screen readers, and the tooltip unless `title` is given. */
  label: string;
  title?: string;
  onClick: () => void;
  disabled?: boolean;
  /** For toggles: whether the panel or mode is on. Leave out for plain actions. */
  pressed?: boolean;
  onPointerDown?: (event: ReactPointerEvent<HTMLButtonElement>) => void;
  onMouseDown?: (event: ReactMouseEvent<HTMLButtonElement>) => void;
};

function IconButton({ icon, label, title, onClick, disabled = false, pressed, onPointerDown, onMouseDown }: IconButtonProps) {
  return (
    <button
      type="button"
      onPointerDown={onPointerDown}
      onMouseDown={onMouseDown}
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      aria-pressed={pressed}
      title={title ?? label}
      className={`${iconBtnCls} ${pressed ? activeCls : ""} ${disabled ? disabledCls : ""}`}
    >
      <span aria-hidden="true">{icon}</span>
    </button>
  );
}

function Divider() {
  return <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1.5" />;
}

const btnCls =
  "px-2 py-0.5 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors";

const iconBtnCls =
  "inline-flex items-center justify-center w-7 h-7 rounded text-base leading-none text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors";

const activeCls = "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300";

const disabledCls = "opacity-40 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent";

function buttonClass(disabled: boolean) {
  return disabled ? `${btnCls} ${disabledCls}` : btnCls;
}
