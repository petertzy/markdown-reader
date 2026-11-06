// shortcut-groups.mjs
// Splits the shortcut list into File / Edit / Format / View columns for the
// Shortcuts menu. Plain .mjs (not .ts) so the Node test suite can import it.

/** Column order, and which action id prefixes belong in each column. */
export const SHORTCUT_CATEGORIES = [
  { heading: "File", prefixes: ["file."] },
  { heading: "Edit", prefixes: ["edit."] },
  { heading: "Format", prefixes: ["format.", "table."] },
  { heading: "View", prefixes: ["view."] },
];

// Within a column, actions listed here come first in this order; anything
// else keeps its original order after them.
const PREFERRED_ORDER = [
  "file.new",
  "file.open",
  "file.openFolder",
  "file.save",
  "file.closeTab",
  "file.closeAllTabs",
  "file.exportHtml",
  "file.exportPdf",
  "file.exportDocx",
  "format.bold",
  "format.italic",
  "format.underline",
  "format.heading1",
  "format.heading2",
  "format.heading3",
  "format.normal",
  "table.insert",
];

/**
 * @template {{ id: string }} T
 * @param {T[]} shortcuts
 * @returns {{ heading: string, items: T[] }[]} non-empty columns only
 */
export function groupShortcuts(shortcuts) {
  const rank = (id) => {
    const i = PREFERRED_ORDER.indexOf(id);
    return i === -1 ? PREFERRED_ORDER.length : i;
  };
  const columns = SHORTCUT_CATEGORIES.map((category) => ({
    heading: category.heading,
    items: shortcuts
      .map((shortcut, index) => ({ shortcut, index }))
      .filter(({ shortcut }) => category.prefixes.some((p) => shortcut.id.startsWith(p)))
      .sort((a, b) => rank(a.shortcut.id) - rank(b.shortcut.id) || a.index - b.index)
      .map(({ shortcut }) => shortcut),
  }));

  // Anything with an unknown prefix still shows up, in an "Other" column.
  const known = new Set(columns.flatMap((c) => c.items));
  const other = shortcuts.filter((s) => !known.has(s));
  if (other.length) columns.push({ heading: "Other", items: other });

  return columns.filter((c) => c.items.length > 0);
}
