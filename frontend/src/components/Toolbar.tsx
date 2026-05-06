"use client";

/**
 * Toolbar.tsx
 * ===========
 * Top action bar: file open/save, export, view toggles, settings.
 */

type Props = {
  onOpenFile: () => void;
  onSaveFile: () => void;
  onExport: (format: "html" | "pdf" | "docx") => void;
  onToggleDark: () => void;
  onToggleAIPanel: () => void;
  darkMode: boolean;
  fontSize: number;
  onFontSizeChange: (size: number) => void;
  showAIPanel: boolean;
  backendStatus?: "starting" | "ready" | "error";
  backendMessage?: string | null;
};

export default function Toolbar({
  onOpenFile,
  onSaveFile,
  onExport,
  onToggleDark,
  onToggleAIPanel,
  darkMode,
  fontSize,
  onFontSizeChange,
  showAIPanel,
  backendStatus = "ready",
  backendMessage = null,
}: Props) {
  const backendBusy = backendStatus === "starting";
  const backendFailed = backendStatus === "error";
  const backendDisabled = backendBusy || backendFailed;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-[#252526] border-b border-gray-200 dark:border-gray-700 shrink-0 text-sm">
      {/* File ops */}
      <button onClick={onOpenFile} className={buttonClass(backendDisabled)} title="Open file" disabled={backendDisabled}>
        📂 Open
      </button>
      <button onClick={onSaveFile} className={buttonClass(backendDisabled)} title="Save (Ctrl+S)" disabled={backendDisabled}>
        💾 Save
      </button>

      <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1" />

      {/* Export */}
      <span className="text-gray-400 text-xs">Export:</span>
      {(["html", "pdf", "docx"] as const).map((fmt) => (
        <button key={fmt} onClick={() => onExport(fmt)} className={buttonClass(backendDisabled)} disabled={backendDisabled}>
          {fmt.toUpperCase()}
        </button>
      ))}

      <div className="w-px h-5 bg-gray-300 dark:bg-gray-600 mx-1" />

      {/* Font size */}
      <span className="text-gray-500 dark:text-gray-400 text-xs">Font:</span>
      <button onClick={() => onFontSizeChange(Math.max(10, fontSize - 1))} className={btnCls}>A-</button>
      <span className="text-xs text-gray-600 dark:text-gray-300 w-5 text-center">{fontSize}</span>
      <button onClick={() => onFontSizeChange(Math.min(32, fontSize + 1))} className={btnCls}>A+</button>

      <div className="flex-1" />

      {backendBusy && (
        <span className="text-xs text-amber-600 dark:text-amber-300 whitespace-nowrap">
          Starting local engine...
        </span>
      )}
      {backendFailed && (
        <span className="text-xs text-red-600 dark:text-red-300 truncate max-w-[220px]" title={backendMessage ?? undefined}>
          Local engine unavailable
        </span>
      )}

      {/* Toggles */}
      <button
        onClick={onToggleAIPanel}
        className={`${btnCls} ${showAIPanel ? "bg-blue-100 dark:bg-blue-900/40 text-blue-700 dark:text-blue-300" : ""}`}
        title="AI Assistant"
      >
        🤖 AI
      </button>
      <button onClick={onToggleDark} className={btnCls} title="Toggle dark mode">
        {darkMode ? "☀️" : "🌙"}
      </button>
    </div>
  );
}

const btnCls =
  "px-2 py-0.5 rounded text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-[#2d2d2d] transition-colors";

function buttonClass(disabled: boolean) {
  return disabled
    ? `${btnCls} opacity-40 cursor-not-allowed hover:bg-transparent dark:hover:bg-transparent`
    : btnCls;
}
