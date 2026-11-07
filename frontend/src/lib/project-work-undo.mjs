/**
 * Undo support for accepted Project Work results.
 *
 * Accepting Project Work rewrites the content of several editor tabs (and may
 * open new ones). Those writes go through React state, not one Monaco model, so
 * the editor's own Undo cannot step back over them. Instead we snapshot every
 * tab the result is about to touch, and revert from that snapshot on request.
 *
 * @typedef {{ id: string, filePath: string | null, content: string, dirty: boolean }} TabLike
 * @typedef {{ file_path: string, content: string }} ChangeLike
 * @typedef {{
 *   filePath: string,
 *   applied: string,
 *   before: { content: string, dirty: boolean } | null,
 * }} ProjectWorkUndoEntry
 */

/**
 * Record the state of every tab a Project Work result is about to change.
 * `before` is null for files the result opens as new tabs.
 *
 * @param {TabLike[]} tabs
 * @param {ChangeLike[]} changes
 * @returns {ProjectWorkUndoEntry[]}
 */
export function captureProjectWorkUndo(tabs, changes) {
  return changes.map((change) => {
    const tab = tabs.find((candidate) => candidate.filePath === change.file_path);
    return {
      filePath: change.file_path,
      applied: change.content,
      before: tab ? { content: tab.content, dirty: tab.dirty } : null,
    };
  });
}

/**
 * Restore the tabs recorded by `captureProjectWorkUndo`.
 *
 * A tab is only reverted while it still holds exactly the AI content, so undo
 * never throws away edits the user made afterwards. Such tabs, and new tabs
 * that were already saved to disk, are left alone and reported in `skipped`.
 * A reverted tab whose AI content was saved stays dirty, because the file on
 * disk no longer matches the restored text.
 *
 * @template {TabLike} T
 * @param {T[]} tabs
 * @param {ProjectWorkUndoEntry[]} record
 * @returns {{ tabs: T[], reverted: string[], skipped: string[] }}
 */
export function revertProjectWork(tabs, record) {
  let next = tabs;
  const reverted = [];
  const skipped = [];

  for (const entry of record) {
    const tab = next.find((candidate) => candidate.filePath === entry.filePath);
    if (!tab) continue; // Closed since apply: nothing left to revert.
    if (tab.content !== entry.applied || (!entry.before && !tab.dirty)) {
      skipped.push(entry.filePath);
      continue;
    }
    const before = entry.before;
    next = before
      ? next.map((candidate) =>
          candidate === tab
            ? { ...candidate, content: before.content, dirty: tab.dirty ? before.dirty : true }
            : candidate
        )
      : next.filter((candidate) => candidate !== tab);
    reverted.push(entry.filePath);
  }

  return { tabs: next, reverted, skipped };
}
