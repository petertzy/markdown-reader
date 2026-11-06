/**
 * The single source of truth for keyboard shortcuts.
 *
 * Both the global keydown handler (useKeyboardShortcuts) and the Shortcuts menu
 * read this table, so a binding cannot work without being listed or be listed
 * without working. It is plain JavaScript so the frontend test suite (Node 20,
 * no TypeScript loader) can check the real table for conflicts on every
 * platform.
 *
 * @typedef {{ key: string, code?: string, ctrl?: boolean, meta?: boolean, shift?: boolean, alt?: boolean }} Binding
 * @typedef {{ id: string, label: string, scope: "global" | "editor", bindings: Binding[] }} Definition
 */

const NAMED_KEY_CODES = { "=": "Equal", "-": "Minus" };

/** Physical key code, so a chord still matches when a layout changes `key`. */
export function keyCodeFor(key) {
  if (/^[a-z]$/i.test(key)) return `Key${key.toUpperCase()}`;
  if (/^\d$/.test(key)) return `Digit${key}`;
  return NAMED_KEY_CODES[key];
}

/**
 * Build the shortcut table for one platform.
 *
 * Shortcuts are listed category by category (file, edit, format, table, view,
 * tab); the Shortcuts menu separates them where the id prefix changes.
 *
 * @param {boolean} isMac
 * @returns {Definition[]}
 */
export function buildDefaultShortcuts(isMac) {
  /** Cmd on macOS, Ctrl elsewhere. */
  const primary = (key, extra = {}) => ({
    key,
    code: keyCodeFor(key),
    ...(isMac ? { meta: true } : { ctrl: true }),
    ...extra,
  });
  const primaryAlt = (key) => primary(key, { alt: true });

  return [
    { id: "file.new", label: "New File", scope: "global", bindings: [primary("n")] },
    { id: "file.open", label: "Open File", scope: "global", bindings: [primary("o")] },
    { id: "file.openFolder", label: "Open Folder", scope: "global", bindings: [primary("o", { shift: true })] },
    { id: "file.save", label: "Save File", scope: "global", bindings: [primary("s")] },
    { id: "file.exportHtml", label: "Export to HTML", scope: "editor", bindings: [primaryAlt("h")] },
    { id: "file.exportDocx", label: "Export to Word", scope: "editor", bindings: [primaryAlt("d")] },
    { id: "file.exportPdf", label: "Export to PDF", scope: "editor", bindings: [primaryAlt("p")] },
    { id: "file.closeTab", label: "Close Current Tab", scope: "global", bindings: [primary("w")] },
    { id: "file.closeAllTabs", label: "Close All Tabs", scope: "global", bindings: [primary("w", { shift: true })] },

    // Undo/redo drive the document editor (useActions maps them to
    // runMonacoAction), so they are scoped to the editor like every other
    // `edit.*` / `format.*` command. With `scope: "global"` they also fired while
    // typing in the AI panel's chat and work-instruction textareas and in the
    // settings inputs: preventDefault killed the field's native undo, then focus
    // jumped to Monaco and undid a document edit instead.
    { id: "edit.undo", label: "Undo", scope: "editor", bindings: [primary("z")] },
    {
      id: "edit.redo",
      label: "Redo",
      scope: "editor",
      bindings: isMac
        ? [primary("z", { shift: true })]
        : [{ key: "y", ctrl: true }, primary("z", { shift: true })],
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
    { id: "format.strikethrough", label: "Strikethrough", scope: "editor", bindings: [primary("x", { shift: true })] },
    { id: "format.inlineCode", label: "Inline Code", scope: "editor", bindings: [primary("e")] },
    { id: "format.link", label: "Insert Link", scope: "editor", bindings: [primary("k")] },
    { id: "format.heading1", label: "Heading 1", scope: "editor", bindings: [primary("1")] },
    { id: "format.heading2", label: "Heading 2", scope: "editor", bindings: [primary("2")] },
    { id: "format.heading3", label: "Heading 3", scope: "editor", bindings: [primary("3")] },
    { id: "format.normal", label: "Normal Text", scope: "editor", bindings: [primary("0")] },

    { id: "table.insert", label: "Insert Table", scope: "editor", bindings: [primaryAlt("t")] },

    { id: "view.toggleDarkMode", label: "Toggle Dark Mode", scope: "global", bindings: [{ key: "F6" }] },
    { id: "view.toggleFocusMode", label: "Toggle Focus Mode", scope: "global", bindings: [{ key: "F8" }] },
    // Editor scope: in the app's own text fields Ctrl+Shift+V stays "paste".
    { id: "view.showPreview", label: "Toggle Preview Panel", scope: "editor", bindings: [primary("v", { shift: true })] },
    { id: "view.toggleAIPanel", label: "Toggle AI Agent Panel", scope: "global", bindings: [primary("a", { shift: true })] },
    { id: "view.openBrowserPreview", label: "Open Preview in Browser", scope: "global", bindings: [primaryAlt("b")] },
    { id: "view.increaseFontSize", label: "Increase Font Size", scope: "global", bindings: [primary("=")] },
    { id: "view.decreaseFontSize", label: "Decrease Font Size", scope: "global", bindings: [primary("-")] },
    { id: "view.fullEditor", label: "Full Width Editor", scope: "global", bindings: [primaryAlt("ArrowLeft")] },
    { id: "view.balancedSplit", label: "Balanced Split View", scope: "global", bindings: [primaryAlt("ArrowDown")] },
    { id: "view.fullPreview", label: "Full Width Preview", scope: "global", bindings: [primaryAlt("ArrowRight")] },

    // Ctrl+Tab is the tab-switching convention on every platform, macOS included.
    { id: "tab.next", label: "Next Tab", scope: "global", bindings: [{ key: "Tab", ctrl: true }] },
    { id: "tab.previous", label: "Previous Tab", scope: "global", bindings: [{ key: "Tab", ctrl: true, shift: true }] },
  ];
}

/** Canonical string for a chord, used to detect two shortcuts sharing one. */
export function bindingSignature(binding) {
  const mods = ["ctrl", "meta", "alt", "shift"].filter((mod) => binding[mod]);
  return [...mods, binding.key.toLowerCase()].join("+");
}
