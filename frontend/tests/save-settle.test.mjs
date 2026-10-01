import { test } from "node:test";
import assert from "node:assert/strict";

// Exercises the real helper the app imports. `useEditor.ts` is TypeScript and CI
// runs the frontend suite on Node 20, which cannot import `.ts`, so the rule
// lives in `src/lib/save-settle.mjs` (same pattern as http-timeout.mjs).
import { fileNameOf, settleSavedTab } from "../src/lib/save-settle.mjs";

const WRITTEN = "# Title\n\nBody as it was when the save started.\n";

test("fileNameOf returns the filename for either separator", () => {
  assert.equal(fileNameOf("/work/notes/report.md"), "report.md");
  assert.equal(fileNameOf("C:\\notes\\report.md"), "report.md");
  assert.equal(fileNameOf("report.md"), "report.md");
});

test("a save with no intervening edits clears the dirty flag", () => {
  const patch = settleSavedTab({
    writtenContent: WRITTEN,
    currentContent: WRITTEN,
    savedPath: "/work/notes/report.md",
  });
  assert.equal(patch.dirty, false);
  assert.equal(patch.filePath, "/work/notes/report.md");
  assert.equal(patch.label, "report.md");
});

test("text typed while the write was in flight keeps the tab dirty", () => {
  // The write is an HTTP round trip. Everything the user typed after the
  // snapshot was sent is not on disk, so reporting "saved" would lose it.
  const typedDuringWrite = WRITTEN + "\nAnd a line added mid-flight.\n";
  const patch = settleSavedTab({
    writtenContent: WRITTEN,
    currentContent: typedDuringWrite,
    savedPath: "/work/notes/report.md",
  });
  assert.equal(patch.dirty, true, "unwritten edits must stay marked dirty");
  assert.equal(patch.filePath, "/work/notes/report.md", "the path is still adopted");
  assert.equal(patch.label, "report.md");
});

test("a deletion made during the write also keeps the tab dirty", () => {
  // Comparison is on the whole buffer, so removing text is caught too.
  const patch = settleSavedTab({
    writtenContent: WRITTEN,
    currentContent: "# Title\n",
    savedPath: "/work/notes/report.md",
  });
  assert.equal(patch.dirty, true);
});

test("two different buffers with equal length are not confused", () => {
  const a = "# Title\n\nAAAA\n";
  const b = "# Title\n\nBBBB\n";
  assert.equal(a.length, b.length);
  const patch = settleSavedTab({
    writtenContent: a,
    currentContent: b,
    savedPath: "/work/notes/report.md",
  });
  assert.equal(patch.dirty, true);
});

test("an empty buffer saved as empty is clean", () => {
  const patch = settleSavedTab({
    writtenContent: "",
    currentContent: "",
    savedPath: "/work/notes/new.md",
  });
  assert.equal(patch.dirty, false);
  assert.equal(patch.label, "new.md");
});

test("saving to a new path still renames the tab", () => {
  // A converted document has no path until its first save, so the label and
  // path adoption have to work even though there is no prior file.
  const patch = settleSavedTab({
    writtenContent: WRITTEN,
    currentContent: WRITTEN,
    savedPath: "/elsewhere/converted.md",
  });
  assert.equal(patch.dirty, false);
  assert.equal(patch.label, "converted.md");
  assert.equal(patch.filePath, "/elsewhere/converted.md");
});
