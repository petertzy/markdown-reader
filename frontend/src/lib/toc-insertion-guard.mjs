/**
 * Capture the editor state that owns an asynchronous table-of-contents request.
 * A completed request may only write back to this exact, unchanged insertion
 * target; otherwise a tab switch or user edit could receive stale content.
 */
export function captureTocInsertionTarget(editor) {
  const model = editor?.getModel();
  const selection = editor?.getSelection();
  if (!editor || !model || !selection) return null;

  return {
    editor,
    model,
    versionId: model.getVersionId(),
    selection: {
      startLineNumber: selection.startLineNumber,
      startColumn: selection.startColumn,
      endLineNumber: selection.endLineNumber,
      endColumn: selection.endColumn,
    },
  };
}

/** Return whether an asynchronous TOC result still has its original target. */
export function isTocInsertionTargetCurrent(target, editor) {
  if (!target || editor !== target.editor || editor.getModel() !== target.model) return false;
  if (target.model.getVersionId() !== target.versionId) return false;

  const selection = editor.getSelection();
  return Boolean(
    selection &&
      selection.startLineNumber === target.selection.startLineNumber &&
      selection.startColumn === target.selection.startColumn &&
      selection.endLineNumber === target.selection.endLineNumber &&
      selection.endColumn === target.selection.endColumn
  );
}
