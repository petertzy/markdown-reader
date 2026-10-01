import { test } from "node:test";
import assert from "node:assert/strict";

// Exercises the real helper the app imports, so this regression suite fails if
// the base-directory rule regresses. `useEditor.ts` is TypeScript and CI runs the
// frontend suite on Node 20, which cannot import `.ts`, so the decision itself
// lives in `src/lib/preview-base-dir.mjs` (same pattern as http-timeout.mjs).
import { parentDirOf, resolvePreviewBaseDir } from "../src/lib/preview-base-dir.mjs";

// A plain Markdown tab: the folder is derived from `filePath`.
const MD_FILE = "/work/notes/report.md";

// A tab opened from report.html. `filePath` is deliberately null so Save asks
// for a destination instead of overwriting the source file, but the converted
// Markdown keeps the relative image paths from that folder.
const IMPORTED_DIR = "/work/notes/";
const IMPORTED_FILE = null;

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