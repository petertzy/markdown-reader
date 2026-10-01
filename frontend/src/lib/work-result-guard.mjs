/**
 * Snapshot of the document that an AI Work request was based on.
 * @typedef {{ documentId: string, content: string }} WorkDocumentSnapshot
 */

/**
 * Return true only when the current document is still the same document and
 * content that the AI Work request was based on.
 *
 * @param {WorkDocumentSnapshot} requestSnapshot
 * @param {WorkDocumentSnapshot} currentSnapshot
 */
export function isWorkResultFresh(requestSnapshot, currentSnapshot) {
  return (
    requestSnapshot.documentId === currentSnapshot.documentId &&
    requestSnapshot.content === currentSnapshot.content
  );
}

/**
 * Apply an AI Work result only when it is still based on the active document's
 * current snapshot.
 *
 * @param {WorkDocumentSnapshot} requestSnapshot
 * @param {WorkDocumentSnapshot} currentSnapshot
 * @param {string} modifiedContent
 * @param {(content: string) => void} onApply
 */
export function applyWorkResultIfFresh(
  requestSnapshot,
  currentSnapshot,
  modifiedContent,
  onApply
) {
  if (!isWorkResultFresh(requestSnapshot, currentSnapshot)) return false;
  onApply(modifiedContent);
  return true;
}
