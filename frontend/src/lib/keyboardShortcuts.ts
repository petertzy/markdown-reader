"use client";

import { buildDefaultShortcuts } from "@/lib/shortcut-definitions.mjs";

export type ActionId =
  | "file.new"
  | "file.open"
  | "file.openFolder"
  | "file.save"
  | "file.closeTab"
  | "file.closeAllTabs"
  | "file.exportHtml"
  | "file.exportPdf"
  | "file.exportDocx"
  | "edit.undo"
  | "edit.redo"
  | "edit.search"
  | "edit.replace"
  | "format.bold"
  | "format.italic"
  | "format.underline"
  | "format.heading1"
  | "format.heading2"
  | "format.heading3"
  | "format.normal"
  | "format.strikethrough"
  | "format.inlineCode"
  | "format.link"
  | "table.insert"
  | "view.toggleDarkMode"
  | "view.toggleAIPanel"
  | "view.showPreview"
  | "view.openBrowserPreview"
  | "view.fullEditor"
  | "view.balancedSplit"
  | "view.fullPreview"
  | "view.toggleFocusMode"
  | "view.increaseFontSize"
  | "view.decreaseFontSize"
  | "tab.next"
  | "tab.previous";

export type ShortcutBinding = {
  key: string;
  code?: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
};

export type ShortcutDefinition = {
  id: ActionId;
  label: string;
  bindings: ShortcutBinding[];
  scope: "global" | "editor";
};

export type ShortcutOverrideMap = Partial<Record<ActionId, ShortcutBinding[]>>;

const isMac =
  typeof navigator !== "undefined" &&
  (/Mac|iPhone|iPad|iPod/i.test(navigator.platform) || /Mac/i.test(navigator.userAgent));

// The table itself lives in shortcut-definitions.mjs so tests can check it.
export const DEFAULT_SHORTCUTS = buildDefaultShortcuts(isMac) as ShortcutDefinition[];

export function resolveShortcutDefinitions(
  overrides: ShortcutOverrideMap = {}
): ShortcutDefinition[] {
  return DEFAULT_SHORTCUTS.map((shortcut) => ({
    ...shortcut,
    bindings: overrides[shortcut.id] ?? shortcut.bindings,
  }));
}

export function shortcutMatchesEvent(binding: ShortcutBinding, event: KeyboardEvent) {
  const keyMatches = event.key.toLowerCase() === binding.key.toLowerCase();
  const codeMatches = Boolean(binding.code && event.code === binding.code);

  return (
    (keyMatches || codeMatches) &&
    event.ctrlKey === Boolean(binding.ctrl) &&
    event.metaKey === Boolean(binding.meta) &&
    event.shiftKey === Boolean(binding.shift) &&
    event.altKey === Boolean(binding.alt)
  );
}

/**
 * Whether an IME-composing keydown should be ignored for a given binding.
 *
 * Genuine IME composition must never fire an app shortcut. On some layouts
 * (e.g. Windows AltGr) a composing chord is reported with both `ctrlKey` and
 * `altKey` set, and because our `Ctrl+Alt+…` bindings match on the physical
 * `code` ({@link shortcutMatchesEvent}), those chords could otherwise hit e.g.
 * `Ctrl+Alt+T` (insert table). We therefore keep Alt-involving bindings blocked
 * while a composition is in progress.
 *
 * WebKit/Tauri in the packaged app can spuriously report `isComposing === true`
 * for plain Ctrl/Meta chords (the false-positive the packaged-app fix exists to
 * work around). Those never involve Alt, so we only trust `isComposing` to
 * block bindings that require Alt — non-Alt shortcuts still match and continue
 * to work even when `isComposing` is wrongly set.
 */
export function isCompositionBlocked(
  binding: ShortcutBinding,
  event: Pick<KeyboardEvent, "isComposing">
): boolean {
  return event.isComposing && Boolean(binding.alt);
}

export function formatShortcut(binding?: ShortcutBinding) {
  if (!binding) return "";
  const parts: string[] = [];
  if (binding.meta) parts.push("Cmd");
  if (binding.ctrl) parts.push("Ctrl");
  if (binding.alt) parts.push(isMac ? "Option" : "Alt");
  if (binding.shift) parts.push("Shift");
  parts.push(binding.key.length === 1 ? binding.key.toUpperCase() : binding.key);
  return parts.join("+");
}

export function isEditableTarget(target: EventTarget | null) {
  if (!(target instanceof HTMLElement)) return false;
  const tagName = target.tagName.toLowerCase();
  return tagName === "input" || tagName === "textarea" || target.isContentEditable;
}
