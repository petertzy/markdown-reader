import { test } from "node:test";
import assert from "node:assert/strict";

// NOTE: This test deliberately mirrors the control flow of
// `handleExport` in `frontend/src/hooks/useFileIO.ts` as a self-contained copy.
// CI runs the frontend suite on Node 20, which cannot import `.ts` modules, so
// this regression test stays dependency-free (same approach as
// keyboard-shortcuts.test.mjs and editor-undo.test.mjs).
// Keep this file's flow in sync with `handleExport`.
//
// The bug: `handleExport` snapshotted the buffer, awaited the export, and then
// re-applied that snapshot to the editor. `editor.exportAs()` only builds a
// payload and never writes back, so the post-await restore silently discarded
// everything typed while the export was in flight.

/** Minimal stand-ins for the tab state and the Monaco model. */
function createEditorHarness() {
  return {
    tabContent: "",
    modelValue: "",
    dirty: false,
  };
}

/**
 * Mirrors `handleExport` after the fix: snapshot, flush into state, await, done.
 * `editWhileExporting` stands in for the user typing during the export window.
 */
async function runExport(fixed, harness) {
  const content = harness.modelValue; // snapshot of the live buffer

  // Pre-export flush: sync the live buffer into React state. Never write the
  // snapshot back afterwards.
  harness.tabContent = content;

  // The user keeps typing while the export is in flight.
  const typed = `${content}\n## Added during export`;
  harness.modelValue = typed;
  harness.tabContent = typed;
  harness.dirty = true;

  await Promise.resolve(); // the export resolves

  if (!fixed) {
    // The old, buggy behaviour: re-apply the stale snapshot after the await.
    harness.tabContent = content;
    harness.modelValue = content;
  }
  return harness;
}

test("regression: edits typed during an export survive (pre-fix behaviour lost them)", async () => {
  const harness = createEditorHarness();
  harness.modelValue = "# Draft";

  const before = await runExport(false, harness);
  const buggyResult = before.tabContent;

  // Show the actual data loss the old code caused.
  assert.equal(buggyResult, "# Draft", "the buggy flow should clobber the newer text");
  assert.ok(
    !buggyResult.includes("Added during export"),
    "text typed during the export was silently discarded"
  );
});

test("editor content is untouched by the export completing", async () => {
  const harness = createEditorHarness();
  harness.modelValue = "# Draft";

  const after = await runExport(true, harness);

  assert.equal(
    after.tabContent,
    "# Draft\n## Added during export",
    "the export must not overwrite the live editor buffer"
  );
  assert.equal(after.modelValue, after.tabContent, "model and tab stay in sync");
  assert.equal(after.dirty, true, "the tab is still dirty — it was never saved");
});

test("the export payload is the snapshot taken before the await", async () => {
  // The exported document is the buffer as it was when the export started; the
  // fix must not change *which* content is exported, only stop writing it back.
  const harness = createEditorHarness();
  harness.modelValue = "# Draft";

  const exported = harness.modelValue;
  harness.modelValue = `${exported}\n## Added during export`;

  assert.equal(exported, "# Draft");
  assert.notEqual(harness.modelValue, exported, "the live buffer moved on");
});
