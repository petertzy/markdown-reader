/**
 * preview-base-dir.mjs
 * ====================
 * Chooses the `base_dir` sent to the render endpoint for a tab.
 *
 * Kept as a plain ESM module (no TypeScript) so the Node-based regression suite
 * (node:test, .mjs) can exercise the exact code the app runs.
 */

/**
 * Directory part of a file path, using either separator, or `undefined` when
 * the path has no directory component.
 *
 * The backend resolves relative image sources with
 * `os.path.abspath(os.path.join(base_dir, src))`, so this must be the folder
 * that actually holds the document — not the previously active tab's folder.
 *
 * @param {string | null | undefined} filePath
 * @returns {string | undefined}
 */
export function parentDirOf(filePath) {
  if (!filePath) return undefined;
  const dir = String(filePath).replace(/[^/\\]+$/, "");
  return dir || undefined;
}

/**
 * Resolve the base directory for a preview render.
 *
 * `override` is an explicit argument at the call site and always wins. Failing
 * that, a tab's own `previewBaseDir` is used: a document imported from
 * `.html`/`.pdf`/`.docx` is converted on open and deliberately keeps
 * `filePath === null` (so Save asks for a destination instead of overwriting
 * the source file), yet its relative image paths still belong to the folder it
 * was imported from. `filePath` is the last resort, which is what plain
 * Markdown tabs use.
 *
 * `previewBaseDir` and `filePath` are passed separately rather than as a tab
 * object so the caller can list them individually in its `useCallback` deps.
 *
 * @param {string | null | undefined} override
 * @param {string | null | undefined} previewBaseDir
 * @param {string | null | undefined} filePath
 * @returns {string | undefined}
 */
export function resolvePreviewBaseDir(override, previewBaseDir, filePath) {
  if (override) return override;
  if (previewBaseDir) return previewBaseDir;
  return parentDirOf(filePath);
}