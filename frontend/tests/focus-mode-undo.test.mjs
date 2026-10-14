import { test } from "node:test";
import assert from "node:assert/strict";

// NOTE: Mirrors the `edit.undo` / `edit.redo` routing in
// `frontend/src/hooks/editor/useActions.ts` (issue #341) as a self-contained
// copy, because CI runs the frontend suite on Node 20 which cannot import
// `.ts` modules (same approach as keyboard-shortcuts.test.mjs).
// Keep this file's logic in sync with useActions.ts.

// Mirror of the dispatch decision inside the `actions` memo: while the
// FocusModePane handle is published (Focus Mode mounted), undo/redo must go to
// Milkdown; otherwise they fall back to the Monaco-backed runMonacoAction.
function dispatchUndoRedo(id, { focusEditor, runMonacoAction }) {
  assert.ok(id === "edit.undo" || id === "edit.redo", "only undo/redo route through here");
  if (focusEditor) {
    focusEditor[id === "edit.undo" ? "undo" : "redo"]();
    return "focus-editor";
  }
  runMonacoAction(id === "edit.undo" ? "undo" : "redo");
  return "monaco";
}

test("Focus Mode mounted: undo routes to the Milkdown handle, not the (null) Monaco ref", () => {
  const calls = [];
  const focusEditor = {
    undo: () => calls.push("milkdown-undo"),
    redo: () => calls.push("milkdown-redo"),
  };
  // runMonacoAction would silently no-op in Focus Mode (monacoRef.current is
  // null) — it must NOT be the path taken.
  const runMonacoAction = (a) => calls.push(`monaco-${a}`);

  assert.equal(dispatchUndoRedo("edit.undo", { focusEditor, runMonacoAction }), "focus-editor");
  assert.deepEqual(calls, ["milkdown-undo"]);

  assert.equal(dispatchUndoRedo("edit.redo", { focusEditor, runMonacoAction }), "focus-editor");
  assert.deepEqual(calls, ["milkdown-undo", "milkdown-redo"]);
});

test("Focus Mode unmounted (handle null): undo/redo fall back to Monaco", () => {
  const calls = [];
  const runMonacoAction = (a) => calls.push(`monaco-${a}`);

  assert.equal(
    dispatchUndoRedo("edit.undo", { focusEditor: null, runMonacoAction }),
    "monaco"
  );
  assert.equal(
    dispatchUndoRedo("edit.redo", { focusEditor: null, runMonacoAction }),
    "monaco"
  );
  assert.deepEqual(calls, ["monaco-undo", "monaco-redo"]);
});

test("regression: an explicit undefined handle (prop omitted) behaves like unmounted", () => {
  // `focusEditorRef` is optional in UseActionsOptions — `?.current` must not
  // throw and must fall back to Monaco.
  const runMonacoActionCalls = [];
  const opts = { focusEditor: undefined, runMonacoAction: (a) => runMonacoActionCalls.push(a) };
  assert.equal(dispatchUndoRedo("edit.undo", opts), "monaco");
  assert.deepEqual(runMonacoActionCalls, ["undo"]);
});

// Mirror of the FocusModePane unmount contract: after the pane cleans up, the
// shared handle is nulled (identity-guarded) so later actions fall back to
// Monaco instead of driving a destroyed Milkdown editor.
test("unmount cleanup: shared handle is cleared, subsequent undo falls back", () => {
  const shared = { current: { undo() {}, redo() {} } };
  const ownHandle = shared.current;

  // unmount cleanup (identity-guarded)
  if (shared.current === ownHandle) shared.current = null;

  const runMonacoActionCalls = [];
  assert.equal(
    dispatchUndoRedo("edit.undo", { focusEditor: shared.current, runMonacoAction: (a) => runMonacoActionCalls.push(a) }),
    "monaco"
  );
  assert.deepEqual(runMonacoActionCalls, ["undo"]);
});

test("identity guard: a stale instance's cleanup must not null the new instance's handle", () => {
  const shared = { current: null };
  const staleHandle = { undo() {}, redo() {} };
  const freshHandle = { undo() {}, redo() {} };

  // stale instance published, then fresh instance replaced it
  shared.current = staleHandle;
  shared.current = freshHandle;

  // stale instance unmounts (tab switch remount order): identity check skips
  if (shared.current === staleHandle) shared.current = null;

  assert.equal(shared.current, freshHandle, "fresh handle survives stale cleanup");
});
