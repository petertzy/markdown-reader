/**
 * Apply an AI Work result to the mounted Monaco editor as a single, undoable
 * edit.
 *
 * `executeWork` used to push the returned content straight through
 * `onDocumentChange`, which updates React state but leaves the editor's own
 * undo stack untouched — the AI replacement was not an editor operation, so a
 * single Undo could not restore the pre-Work document.
 *
 * Wrapping the full-document replacement in `pushUndoStop()` calls makes the
 * whole AI result ONE undo step: one Undo restores the exact pre-Work document
 * and Redo reapplies the AI result, without merging into the user's previous
 * typing. The edit still flows through the editor's change callback, so the
 * existing state/preview synchronization path is preserved.
 *
 * @typedef {{
 *   getModel: () => { getFullModelRange: () => unknown } | null,
 *   pushUndoStop: () => void,
 *   executeEdits: (source: string, edits: Array<{ range: unknown, text: string, forceMoveMarkers?: boolean }>) => void,
 * }} WorkEditorLike
 */

/**
 * Replace the editor's document with `content` as one undoable edit.
 *
 * @param {object | null} editor mounted Monaco editor (or `null`)
 * @param {(content: string) => void} onFallback applied when no editor/model is
 *   available (focus mode, editor not yet mounted, headless tests)
 * @param {string} content
 * @returns {boolean} true when the editor path was used, false for the fallback
 */
export function applyWorkEdit(editor, onFallback, content) {
  const model = editor?.getModel?.();
  if (
    !editor ||
    !model ||
    typeof editor.executeEdits !== "function" ||
    typeof editor.pushUndoStop !== "function"
  ) {
    onFallback(content);
    return false;
  }

  // The opening stop separates the AI result from whatever the user typed
  // before it; the closing stop seals the replacement into its own undo group.
  editor.pushUndoStop();
  editor.executeEdits("ai-work", [
    { range: model.getFullModelRange(), text: content, forceMoveMarkers: true },
  ]);
  editor.pushUndoStop();
  return true;
}