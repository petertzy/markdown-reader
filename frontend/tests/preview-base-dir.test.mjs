import { test } from "node:test";
import assert from "node:assert/strict";

// Exercises the real helper the app imports, so this regression suite fails if
// the base-directory rule regresses. `useEditor.ts` is TypeScript and CI runs the
// frontend suite on Node 20, which cannot import `.ts`, so the decision itself
// lives in `src/lib/preview-base-dir.mjs` (same pattern as http-timeout.mjs).
import { parentDirOf, resolvePreviewBaseDir } from "../src/lib/preview-base-dir.mjs";
import { resolveTabClose } from "../src/lib/tabLifecycle.mjs";

// A plain Markdown tab: the folder is derived from `filePath`.
const MD_FILE = "/work/notes/report.md";

// A tab opened from report.html. `filePath` is deliberately null so Save asks
// for a destination instead of overwriting the source file, but the converted
// Markdown keeps the relative image paths from that folder.
const IMPORTED_DIR = "/work/notes/";
const IMPORTED_FILE = null;

// A plain Markdown tab: the folder comes from `filePath`, no `previewBaseDir`.
function tab(id, content, filePath) {
  return { id, label: id, content, filePath, dirty: false };
}

test("parentDirOf returns the containing folder, for both separators", () => {
  assert.equal(parentDirOf("/work/notes/report.md"), "/work/notes/");
  assert.equal(parentDirOf("C:\\notes\\report.md"), "C:\\notes\\");
  assert.equal(parentDirOf("/report.md"), "/");
});

test("parentDirOf returns undefined when there is no directory component", () => {
  assert.equal(parentDirOf("report.md"), undefined);
  assert.equal(parentDirOf(""), undefined);
  assert.equal(parentDirOf(null), undefined);
  assert.equal(parentDirOf(undefined), undefined);
});

test("a plain Markdown tab resolves against its own folder", () => {
  assert.equal(resolvePreviewBaseDir(undefined, undefined, MD_FILE), "/work/notes/");
});

test("an explicit override at the call site wins", () => {
  assert.equal(
    resolvePreviewBaseDir("/somewhere/else/", undefined, MD_FILE),
    "/somewhere/else/"
  );
});

test("a converted document resolves against the folder it was imported from", () => {
  // Without `previewBaseDir` there is nothing to fall back to, and every
  // relative image in the converted document would render against the
  // previously active tab's folder (or against the app origin).
  assert.equal(
    resolvePreviewBaseDir(undefined, IMPORTED_DIR, IMPORTED_FILE),
    "/work/notes/"
  );
});

test("previewBaseDir is preferred over filePath when both are present", () => {
  assert.equal(
    resolvePreviewBaseDir(undefined, IMPORTED_DIR, "/elsewhere/report.md"),
    "/work/notes/"
  );
});

test("an untitled tab has no base directory", () => {
  assert.equal(resolvePreviewBaseDir(undefined, undefined, null), undefined);
});

test("missing arguments are handled without throwing", () => {
  assert.equal(resolvePreviewBaseDir(undefined, null, null), undefined);
  assert.equal(resolvePreviewBaseDir(), undefined);
});

test("the backend receives a directory, not a file name", () => {
  // The render endpoint joins base_dir with each relative src, so a file path
  // here would resolve images one level too deep.
  const baseDir = resolvePreviewBaseDir(undefined, IMPORTED_DIR, IMPORTED_FILE);
  assert.ok(!/report\.html$/.test(baseDir), `${baseDir} must not be a file path`);
  assert.ok(baseDir.endsWith("/"), `${baseDir} must keep its trailing separator`);
});

test("an override given as a file path is reduced to its folder", () => {
  // `useEditor.refreshPreview(content, baseDirOverride)` is called with
  // `tab.filePath` on every keystroke, on opening a plain Markdown tab, and on
  // switching tabs, so this is the shape production actually passes.
  assert.equal(resolvePreviewBaseDir(MD_FILE, undefined, MD_FILE), "/work/notes/");
  assert.equal(
    resolvePreviewBaseDir("C:\\notes\\report.md", undefined, undefined),
    "C:\\notes\\"
  );
});

test("an override ending in a separator is preserved", () => {
  assert.equal(
    resolvePreviewBaseDir("/somewhere/else/", undefined, MD_FILE),
    "/somewhere/else/"
  );
  // Without a trailing separator the shared path rule treats the final segment
  // as a document name, so only its parent directory is used.
  assert.equal(resolvePreviewBaseDir("/somewhere/else", undefined, MD_FILE), "/somewhere/");
});

test("an override with no directory component yields no base directory", () => {
  // There is no folder to report, so this answers `undefined` exactly as the
  // `filePath` branch does for the same input.
  assert.equal(resolvePreviewBaseDir("report.md", undefined, MD_FILE), undefined);
});

test("an explicit override wins over previewBaseDir", () => {
  // Precedence is only observable when the two disagree, so both have to be
  // set. Production passes `previewBaseDir ?? filePath` as the override, which
  // never conflicts; this pins the stated rule rather than the call shapes.
  assert.equal(
    resolvePreviewBaseDir("/from/override/", "/from/preview-base-dir/", undefined),
    "/from/override/"
  );
});

test("neither the override nor the file path can yield a file path", () => {
  // `previewBaseDir` is excluded because every call site builds it with
  // `parentDirOf(filePath)`, so it is always a folder or undefined already.
  // The override and `filePath` are the two arguments a caller supplies
  // directly, and either may be given as a document path.
  const inputs = [undefined, null, "", "/work/notes/", "report.md", MD_FILE];
  for (const override of inputs) {
    for (const filePath of inputs) {
      const baseDir = resolvePreviewBaseDir(override, undefined, filePath);
      const label = `o=${override} f=${filePath}`;
      assert.ok(
        baseDir === undefined || /[\\/]$/.test(baseDir),
        `${label} produced a file path: ${baseDir}`
      );
    }
  }
});

test("a converted tab's base dir survives closing the active tab", () => {
  // The converted tab has no `filePath`, so once the user switches back to it
  // the preview can only resolve its relative images if `previewBaseDir` came
  // back through the close result. `tabLifecycle` hands the tab over whole, so
  // the field has to stay visible on `PreviewTab` for `useEditor` to read it.
  const imported = {
    id: "tab-1",
    label: "report.html",
    content: "![](/img/logo.png)",
    filePath: IMPORTED_FILE,
    dirty: false,
    previewBaseDir: IMPORTED_DIR,
  };
  const plain = tab("tab-2", "# Bravo", "/elsewhere/bravo.md");

  // Closing the *plain* tab makes the converted one active again.
  const result = resolveTabClose([imported, plain], "tab-2", "tab-2");

  assert.equal(result.nextActiveTabId, "tab-1");
  assert.ok(result.previewTab, "expected a preview tab to refresh");
  assert.equal(result.previewTab.previewBaseDir, IMPORTED_DIR);
  // With `filePath` null, `previewBaseDir` is the only thing that can resolve the
  // relative image — losing it silently sends every image to the app origin.
  const baseDir = resolvePreviewBaseDir(
    undefined,
    result.previewTab.previewBaseDir,
    result.previewTab.filePath
  );
  assert.equal(baseDir, "/work/notes/");
});
