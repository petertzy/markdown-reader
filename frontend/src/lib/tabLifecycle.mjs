/**
 * tabLifecycle.mjs
 * ================
 * Pure tab lifecycle helpers shared by `useEditor` and the regression suite.
 *
 * Kept as a dependency-free `.mjs` module so the Node 20 CI test runner can
 * import the exact implementation the app uses (same pattern as
 * `http-timeout.mjs`, imported by `src/lib/api.ts`). See
 * `tests/tab-lifecycle.test.mjs`.
 */

/**
 * The subset of `Tab` (`useEditor.ts`) callers of this module consume. Declaring
 * the fields it exposes keeps the helper structurally assignable to `Tab[]`
 * without importing the hook, which Node 20 CI cannot load. Tabs are passed
 * through whole, so every field a caller reads off the result must be declared
 * here even when this module never looks at it.
 *
 * @typedef {object} PreviewTab
 * @property {string} id
 * @property {string} label
 * @property {string} content
 * @property {string | null} filePath
 * @property {boolean} dirty
 * @property {string} [previewBaseDir] Carried through untouched so the caller
 *   can re-render the preview for the tab that becomes active. Omitted from
 *   tabs opened as plain files.
 */

/**
 * @typedef {object} TabCloseResult
 * @property {PreviewTab[]} remaining Tabs left after the close.
 * @property {string | null} nextActiveTabId Tab to activate, or `null` when no
 *   tab is left (the caller then creates a fresh empty tab and clears the
 *   preview).
 * @property {PreviewTab | null} previewTab Tab whose content the preview must
 *   be refreshed with, or `null` when the preview is unaffected by this close.
 */

/**
 * Decide what happens to the tab list, the active tab, and the preview when a
 * tab is closed.
 *
 * The caller applies the React state updates. When the *active* tab is closed
 * the preview pane must be re-rendered for whichever tab becomes active,
 * otherwise it keeps displaying the document that was just closed (the status
 * bar word count stays stale for the same reason).
 *
 * @param {PreviewTab[]} tabs
 * @param {string} activeTabId
 * @param {string} closingTabId
 * @returns {TabCloseResult}
 */
export function resolveTabClose(tabs, activeTabId, closingTabId) {
  const remaining = tabs.filter((tab) => tab.id !== closingTabId);

  // Closing the final tab always leaves one fresh empty tab behind.
  if (remaining.length === 0) {
    return { remaining, nextActiveTabId: null, previewTab: null };
  }

  // Closing an inactive tab changes neither the active tab nor the preview.
  if (closingTabId !== activeTabId) {
    return { remaining, nextActiveTabId: activeTabId, previewTab: null };
  }

  const nextActive = remaining[remaining.length - 1];
  return { remaining, nextActiveTabId: nextActive.id, previewTab: nextActive };
}
