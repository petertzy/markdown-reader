"use client";

export type ActionId =
  | "file.new"
  | "file.open"
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
  | "table.insert"
  | "view.toggleDarkMode"
  | "view.toggleAIPanel";

export type ShortcutBinding = {
  key: string;
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
  typeof navigator !== "undefined" && /Mac|iPhone|iPad|iPod/.test(navigator.platform);

const primary = (key: string, extra: Omit<ShortcutBinding, "key"> = {}): ShortcutBinding => ({
  key,
  ...(isMac ? { meta: true } : { ctrl: true }),
  ...extra,
});

const primaryAlt = (key: string): ShortcutBinding =>
  isMac ? { key, meta: true, alt: true } : { key, ctrl: true, alt: true };

export const DEFAULT_SHORTCUTS: ShortcutDefinition[] = [
  { id: "file.new", label: "New File", scope: "global", bindings: [primary("n")] },
  { id: "file.open", label: "Open File", scope: "global", bindings: [primary("o")] },
  { id: "file.save", label: "Save File", scope: "global", bindings: [primary("s")] },
  { id: "file.closeTab", label: "Close Current Tab", scope: "global", bindings: [primary("w")] },
  {
    id: "file.closeAllTabs",
    label: "Close All Tabs",
    scope: "global",
    bindings: [primary("w", { shift: true })],
  },
  { id: "edit.undo", label: "Undo", scope: "global", bindings: [primary("z")] },
  {
    id: "edit.redo",
    label: "Redo",
    scope: "global",
    bindings: [isMac ? primary("z", { shift: true }) : { key: "y", ctrl: true }],
  },
  { id: "edit.search", label: "Search", scope: "editor", bindings: [primary("f")] },
  {
    id: "edit.replace",
    label: "Replace",
    scope: "editor",
    bindings: [isMac ? primaryAlt("f") : { key: "h", ctrl: true }],
  },
  { id: "format.bold", label: "Bold", scope: "editor", bindings: [primary("b")] },
  { id: "format.italic", label: "Italic", scope: "editor", bindings: [primary("i")] },
  { id: "format.underline", label: "Underline", scope: "editor", bindings: [primary("u")] },
  { id: "format.heading1", label: "Heading 1", scope: "editor", bindings: [primary("1")] },
  { id: "format.heading2", label: "Heading 2", scope: "editor", bindings: [primary("2")] },
  { id: "format.heading3", label: "Heading 3", scope: "editor", bindings: [primary("3")] },
  { id: "format.normal", label: "Normal Text", scope: "editor", bindings: [primary("0")] },
  { id: "table.insert", label: "Insert Table", scope: "editor", bindings: [primaryAlt("t")] },
  { id: "file.exportHtml", label: "Export to HTML", scope: "editor", bindings: [primaryAlt("h")] },
  { id: "file.exportDocx", label: "Export to Word", scope: "editor", bindings: [primaryAlt("d")] },
  { id: "file.exportPdf", label: "Export to PDF", scope: "editor", bindings: [primaryAlt("p")] },
  { id: "view.toggleDarkMode", label: "Toggle Dark Mode", scope: "global", bindings: [{ key: "F6" }] },
  {
    id: "view.toggleAIPanel",
    label: "Toggle AI Agent Panel",
    scope: "global",
    bindings: [primary("a", { shift: true })],
  },
];

export function resolveShortcutDefinitions(
  overrides: ShortcutOverrideMap = {}
): ShortcutDefinition[] {
  return DEFAULT_SHORTCUTS.map((shortcut) => ({
    ...shortcut,
    bindings: overrides[shortcut.id] ?? shortcut.bindings,
  }));
}

export function shortcutMatchesEvent(binding: ShortcutBinding, event: KeyboardEvent) {
  return (
    event.key.toLowerCase() === binding.key.toLowerCase() &&
    event.ctrlKey === Boolean(binding.ctrl) &&
    event.metaKey === Boolean(binding.meta) &&
    event.shiftKey === Boolean(binding.shift) &&
    event.altKey === Boolean(binding.alt)
  );
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
