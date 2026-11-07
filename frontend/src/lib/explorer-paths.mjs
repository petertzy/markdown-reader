/**
 * explorer-paths.mjs
 * ==================
 * Path and open-tab bookkeeping for the project explorer's context menu
 * (issue #455): copy relative path, and keeping editor tabs pointed at the
 * right files after a rename or delete.
 *
 * Kept as a dependency-free `.mjs` module so the Node test runner can import
 * the exact implementation the app uses (same pattern as `tabLifecycle.mjs`).
 * See `tests/explorer-paths.test.mjs`.
 *
 * Paths come from the backend's directory listing, so they use the platform's
 * separator (`\` on Windows, `/` elsewhere). Both are accepted everywhere.
 */

import { parentDirOf } from "./preview-base-dir.mjs";

/** @param {string} path */
function separatorOf(path) {
  return path.includes("\\") && !path.includes("/") ? "\\" : "/";
}

/** @param {string} path */
function trimTrailingSeparators(path) {
  return path.replace(/[/\\]+$/, "");
}

/**
 * Join a folder and a single entry name using the folder's own separator.
 *
 * @param {string} dir
 * @param {string} name
 * @returns {string}
 */
export function joinPath(dir, name) {
  return `${trimTrailingSeparators(dir)}${separatorOf(dir)}${name}`;
}

/**
 * The path a renamed entry ends up at: same folder, new name.
 *
 * @param {string} path
 * @param {string} newName
 * @returns {string}
 */
export function renamedPath(path, newName) {
  const trimmed = trimTrailingSeparators(path);
  const parent = trimmed.replace(/[^/\\]+$/, "");
  return `${parent}${newName}`;
}

/**
 * When `path` is `ancestor` or lies inside it, the part after `ancestor`
 * (empty string for the entry itself, otherwise starting with a separator).
 * `null` when `path` is elsewhere.
 *
 * @param {string | null | undefined} path
 * @param {string} ancestor
 * @returns {string | null}
 */
function suffixWithin(path, ancestor) {
  if (!path) return null;
  const base = trimTrailingSeparators(ancestor);
  if (path === base) return "";
  if (path.startsWith(base) && /[/\\]/.test(path.charAt(base.length))) {
    return path.slice(base.length);
  }
  return null;
}

/**
 * Whether `path` is `ancestor` itself or lies inside it.
 *
 * @param {string | null | undefined} path
 * @param {string} ancestor
 * @returns {boolean}
 */
export function isWithin(path, ancestor) {
  return suffixWithin(path, ancestor) !== null;
}

/**
 * Where `path` ends up after `oldPath` is renamed or moved to `newPath`.
 * Paths outside `oldPath` are returned unchanged.
 *
 * @param {string} path
 * @param {string} oldPath
 * @param {string} newPath
 * @returns {string}
 */
export function remapPath(path, oldPath, newPath) {
  const suffix = suffixWithin(path, oldPath);
  return suffix === null ? path : trimTrailingSeparators(newPath) + suffix;
}

/**
 * Path of `path` relative to the project folder, with the platform's
 * separator kept, e.g. `docs\guide.md`. Returns the path unchanged when it is
 * not inside `root`.
 *
 * @param {string} root
 * @param {string} path
 * @returns {string}
 */
export function relativePath(root, path) {
  const suffix = suffixWithin(path, root);
  if (suffix === null) return path;
  return suffix.replace(/^[/\\]+/, "") || ".";
}

/**
 * The subset of `Tab` (`useEditor.ts`) these helpers read. Tabs are passed
 * through whole, so extra fields survive untouched.
 *
 * @typedef {object} ExplorerTab
 * @property {string} id
 * @property {string} label
 * @property {string | null} filePath
 * @property {string} [sourceFilePath]
 * @property {string} [previewBaseDir]
 * @property {boolean} dirty
 */

/**
 * Point every tab under a renamed or moved file or folder at its new location.
 *
 * Covers the renamed file itself, files inside a renamed folder, and
 * converted documents (`sourceFilePath`). The preview base folder moves with
 * the file so relative images keep resolving. Unaffected tabs are returned as
 * the same objects.
 *
 * @template {ExplorerTab} T
 * @param {T[]} tabs
 * @param {string} oldPath
 * @param {string} newPath
 * @returns {T[]}
 */
export function remapTabsAfterRename(tabs, oldPath, newPath) {
  const target = trimTrailingSeparators(newPath);
  return tabs.map((tab) => {
    const fileSuffix = suffixWithin(tab.filePath, oldPath);
    const sourceSuffix = suffixWithin(tab.sourceFilePath, oldPath);
    if (fileSuffix === null && sourceSuffix === null) return tab;

    const next = { ...tab };
    if (fileSuffix !== null) {
      next.filePath = target + fileSuffix;
      next.label = next.filePath.split(/[/\\]/).pop() ?? next.label;
      next.previewBaseDir = parentDirOf(next.filePath);
    }
    if (sourceSuffix !== null) {
      next.sourceFilePath = target + sourceSuffix;
      next.previewBaseDir = parentDirOf(next.sourceFilePath);
    }
    return next;
  });
}

/**
 * Decide what happens to open tabs when a file or folder is deleted.
 *
 * Tabs with no unsaved changes are closed. Tabs with unsaved changes stay open
 * so the edits are not lost, but are detached from the deleted path
 * (`filePath: null`), so Save asks for a new location instead of silently
 * recreating the deleted file.
 *
 * @template {ExplorerTab} T
 * @param {T[]} tabs
 * @param {string} deletedPath
 * @returns {{ tabs: T[], closeIds: string[] }} `tabs` has the dirty tabs
 *   detached; `closeIds` are the tabs the caller should close.
 */
export function resolveTabsAfterDelete(tabs, deletedPath) {
  /** @type {string[]} */
  const closeIds = [];
  const next = tabs.map((tab) => {
    const affected =
      suffixWithin(tab.filePath, deletedPath) !== null ||
      suffixWithin(tab.sourceFilePath, deletedPath) !== null;
    if (!affected) return tab;
    if (!tab.dirty) {
      closeIds.push(tab.id);
      return tab;
    }
    const detached = { ...tab, filePath: null };
    delete detached.sourceFilePath;
    return detached;
  });
  return { tabs: next, closeIds };
}
