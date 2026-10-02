/**
 * save-settle.mjs
 * ===============
 * Works out what a completed save should do to a tab's state.
 *
 * Kept as a plain ESM module (no TypeScript) so the Node-based regression suite
 * (node:test, .mjs) can exercise the exact code the app runs (same pattern as
 * http-timeout.mjs).
 */

/**
 * Filename portion of a path, using either separator.
 *
 * @param {string} filePath
 * @returns {string}
 */
export function fileNameOf(filePath) {
  return filePath.split(/[/\\]/).pop() ?? filePath;
}

/**
 * Directory portion of a path, using either separator, or `undefined` when the
 * path has no directory component.
 *
 * @param {string} filePath
 * @returns {string | undefined}
 */
export function dirOf(filePath) {
  const dir = String(filePath).replace(/[^/\\]+$/, "");
  return dir || undefined;
}

/**
 * Compute the tab patch for a finished save.
 *
 * The write is a round trip, and the buffer can advance while it is in flight.
 * The content that reached disk is the snapshot taken *before* the request, so
 * clearing `dirty` unconditionally would report edits that were never written as
 * saved. The buffer is authoritative: only clear `dirty` when it still holds
 * exactly what was written.
 *
 * `currentContent` must be read from the latest tab state *after* awaiting the
 * write, not from a value captured before it.
 *
 * `previewBaseDir` is re-pointed at the folder the document was just written to,
 * because saving under a new name moves it and its relative image paths then
 * belong to that folder rather than the one they were authored in. Kept here
 * instead of inlined at the call sites so the rule stays covered by this suite.
 *
 * @param {object} params
 * @param {string} params.writtenContent Content sent to the write call.
 * @param {string} params.currentContent Buffer contents observed after it completed.
 * @param {string} params.savedPath Path the content was written to.
 * @returns {{ dirty: boolean, filePath: string, label: string, previewBaseDir: string | undefined }}
 */
export function settleSavedTab({ writtenContent, currentContent, savedPath }) {
  return {
    // Equal means the buffer still holds exactly what reached disk, so the
    // document is saved. Any difference means edits are still unsaved.
    dirty: currentContent !== writtenContent,
    filePath: savedPath,
    label: fileNameOf(savedPath),
    previewBaseDir: dirOf(savedPath),
  };
}
